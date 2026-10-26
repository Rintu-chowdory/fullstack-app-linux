import express from "express";
import session from "express-session";
import helmet from "helmet";
import multer from "multer";
import axios from "axios";
import path from "path";
import crypto from "crypto";
import fs from "fs";
import ejs from "ejs";
import dotenv from "dotenv";
import { fileURLToPath } from "url";
import MySQLStoreFactory from "express-mysql-session";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = Number(process.env.PORT || 3000);
const API_BASE = process.env.BACKEND_API_BASE_URL || "http://127.0.0.1:8000";
const SESSION_SECRET = process.env.SESSION_SECRET || "";
const TRUST_PROXY = process.env.TRUST_PROXY === "1";
const NODE_ENV = process.env.NODE_ENV || "development";

if (!SESSION_SECRET) {
  console.error("SESSION_SECRET is not set. Refusing to start with guessable sessions.");
  process.exit(1);
}

const app = express();
app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));
app.set("trust proxy", TRUST_PROXY ? 1 : false);

app.use(
  helmet({
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        imgSrc: ["'self'", "data:", API_BASE],
      },
    },
  })
);
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, "public")));

// ------------------------------------------------------- session store
// MariaDB-backed so app1/app2 share sessions (HA requirement).
// Set SESSION_STORE=off to fall back to MemoryStore (single instance only).
let sessionStore;
if (process.env.SESSION_STORE !== "off" && (process.env.DB_HOST || process.env.DATABASE_URL)) {
  const MySQLStore = MySQLStoreFactory(session);
  sessionStore = new MySQLStore({
    host: process.env.DB_HOST || "127.0.0.1",
    port: Number(process.env.DB_PORT || 3306),
    user: process.env.DB_USER || "dipti",
    password: process.env.DB_PASSWORD || "",
    database: process.env.DB_NAME || "dipti_portal",
    clearExpired: true,
    checkExpirationInterval: 900_000,
  });
  console.log("Session store: MariaDB");
} else {
  sessionStore = new session.MemoryStore();
  console.warn("Session store: MEMORY (single-instance fallback; do not use behind the LB)");
}

app.use(
  session({
    name: "dipti.sid",
    store: sessionStore,
    secret: SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.COOKIE_SECURE === "1",
      maxAge: 1000 * 60 * 60, // 1 hour
    },
  })
);

// ------------------------------------------------------- CSRF
app.use((req, res, next) => {
  if (!req.session.csrf) req.session.csrf = crypto.randomBytes(24).toString("hex");
  res.locals.csrf = req.session.csrf;
  next();
});

function requireCsrf(req, res, next) {
  if (req.body._csrf === req.session.csrf) return next();
  res.status(403);
  return renderPage(res, "error", { message: "Invalid or missing CSRF token. Go back and retry." });
}

// ------------------------------------------------------- rate limit (login)
const hits = new Map();
function loginRateLimit(req, res, next) {
  const key = `${req.ip}:${req.path}`;
  const now = Date.now();
  const list = (hits.get(key) || []).filter((t) => now - t < 60_000);
  if (list.length >= 10) {
    res.set("Retry-After", "60");
    return res.status(429).send("Too many attempts. Try again in a minute.");
  }
  list.push(now);
  hits.set(key, list);
  next();
}

// ------------------------------------------------------- view rendering
async function renderPage(res, view, data = {}) {
  const locals = {
    title: data.title || "DIPTI Student Portal",
    student: res.locals.sessionUser?.type === "student" ? res.locals.sessionUser : null,
    admin: res.locals.sessionUser?.type === "admin" ? res.locals.sessionUser : null,
    csrf: res.locals.csrf,
    ...data,
  };
  const body = await ejs.renderFile(path.join(__dirname, "views", `${view}.ejs`), locals);
  res.render("layout", locals, (err, html) => {
    if (err) {
      console.error("layout render error:", err);
      return res.status(500).send("Render error");
    }
    res.send(html.replace("<!--BODY-->", body));
  });
}

app.use((req, res, next) => {
  res.locals.sessionUser = req.session.user || null;
  next();
});

const api = axios.create({ baseURL: API_BASE, timeout: 15000 });

function apiErrorMessage(err) {
  const d = err.response?.data;
  return (
    d?.detail ||
    (typeof d === "string" ? d : null) ||
    (err.code === "ECONNREFUSED" || err.code === "ETIMEDOUT"
      ? "Backend unavailable. Try again shortly."
      : "Request failed")
  );
}

// ------------------------------------------------------- health (for HAProxy/Keepalived checks)
app.get("/healthz", async (req, res) => {
  try {
    await api.get("/readyz", { timeout: 3000 });
    res.json({ status: "ok", backend: "reachable" });
  } catch {
    res.status(503).json({ status: "degraded", backend: "unreachable" });
  }
});

// ------------------------------------------------------- public pages
app.get("/", async (req, res, next) => {
  try {
    await renderPage(res, "index");
  } catch (err) { next(err); }
});

app.get("/student/register", async (req, res, next) => {
  try {
    await renderPage(res, "student_register", { error: null, values: {} });
  } catch (err) { next(err); }
});

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 },
});

app.post("/student/register", upload.single("photo"), requireCsrf, async (req, res, next) => {
  try {
    if (!req.file) {
      return renderPage(res, "student_register", {
        error: "Please choose a profile photo (JPEG/PNG, max 5 MB).",
        values: req.body,
      });
    }
    const form = new FormData();
    for (const f of ["name", "institute", "batch", "course_name", "module", "email", "password"]) {
      form.append(f, req.body[f] || "");
    }
    form.append(
      "photo",
      new Blob([new Uint8Array(req.file.buffer)], { type: req.file.mimetype }),
      req.file.originalname
    );
    await api.post("/api/students/register", form);
    req.session.user = { type: "pending", email: req.body.email };
    return res.redirect("/student/login?registered=1");
  } catch (err) {
    return renderPage(res, "student_register", { error: apiErrorMessage(err), values: req.body });
  }
});

app.get("/student/login", async (req, res, next) => {
  try {
    await renderPage(res, "student_login", { error: null, registered: req.query.registered === "1" });
  } catch (err) { next(err); }
});

app.post("/student/login", loginRateLimit, requireCsrf, async (req, res) => {
  try {
    const r = await api.post("/api/student/login", {
      email: req.body.email,
      password: req.body.password,
    });
    req.session.user = { type: "student", token: r.data.token, email: req.body.email };
    return res.redirect("/student/profile");
  } catch (err) {
    return renderPage(res, "student_login", { error: apiErrorMessage(err), registered: false });
  }
});

app.get("/student/profile", requireStudent, async (req, res, next) => {
  try {
    const r = await api.get("/api/student/me", {
      headers: { Authorization: `Bearer ${req.session.user.token}` },
    });
    await renderPage(res, "student_profile", { me: r.data, photoBase: API_BASE });
  } catch (err) {
    if (err.response?.status === 401) {
      req.session.destroy(() => {});
      return res.redirect("/student/login");
    }
    next(err);
  }
});

app.get("/student/logout", (req, res) => {
  req.session.destroy(() => res.redirect("/"));
});

function requireStudent(req, res, next) {
  if (req.session.user?.type === "student") return next();
  res.redirect("/student/login");
}

function requireAdmin(req, res, next) {
  if (req.session.user?.type === "admin") return next();
  res.redirect("/login");
}

// ------------------------------------------------------- admin pages
app.get("/login", async (req, res, next) => {
  try {
    await renderPage(res, "login", { error: null });
  } catch (err) { next(err); }
});

app.post("/login", loginRateLimit, requireCsrf, async (req, res) => {
  try {
    const r = await api.post("/api/login", {
      username: req.body.username,
      password: req.body.password,
    });
    req.session.user = { type: "admin", token: r.data.token, username: req.body.username };
    return res.redirect("/students");
  } catch (err) {
    return renderPage(res, "login", { error: apiErrorMessage(err) });
  }
});

app.get("/logout", (req, res) => {
  req.session.destroy(() => res.redirect("/"));
});

app.get("/submit", requireAdmin, async (req, res, next) => {
  try {
    await renderPage(res, "form", { error: null, msg: req.query.saved === "1" ? "Saved." : null });
  } catch (err) { next(err); }
});

app.post("/submit", requireAdmin, requireCsrf, async (req, res) => {
  try {
    await api.post(
      "/api/students",
      {
        name: req.body.name,
        institute: req.body.institute,
        batch: req.body.batch,
        course_name: req.body.course_name,
        module: req.body.module,
        email: req.body.email,
      },
      { headers: { Authorization: `Bearer ${req.session.user.token}` } }
    );
    return res.redirect("/submit?saved=1");
  } catch (err) {
    return renderPage(res, "form", { error: apiErrorMessage(err), msg: null });
  }
});

app.get("/students", requireAdmin, async (req, res, next) => {
  try {
    const page = Math.max(1, Number(req.query.page || 1));
    const search = req.query.search || "";
    const r = await api.get("/api/students", {
      params: { page, page_size: 20, search },
      headers: { Authorization: `Bearer ${req.session.user.token}` },
    });
    const totalPages = Math.max(1, Math.ceil(r.data.total / r.data.page_size));
    await renderPage(res, "students", {
      students: r.data.students,
      total: r.data.total,
      page,
      totalPages,
      search,
      photoBase: API_BASE,
    });
  } catch (err) {
    if (err.response?.status === 401) {
      req.session.destroy(() => {});
      return res.redirect("/login");
    }
    next(err);
  }
});

// ------------------------------------------------------- errors
app.use((req, res) => {
  res.status(404);
  renderPage(res, "error", { message: "Page not found." }).catch(() =>
    res.status(404).send("Not found")
  );
});

app.use((err, req, res, _next) => {
  console.error("unhandled error:", err.message);
  res.status(502);
  renderPage(res, "error", { message: "Something went wrong. Try again shortly." }).catch(() =>
    res.status(502).send("Error")
  );
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Frontend listening on http://0.0.0.0:${PORT} (${NODE_ENV})`);
  console.log(`Forwarding API requests to: ${API_BASE}`);
});
