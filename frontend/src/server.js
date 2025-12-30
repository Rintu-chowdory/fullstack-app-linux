import express from "express";
import session from "express-session";
import multer from "multer";
import FormData from "form-data";
import axios from "axios";
import path from "path";
import dotenv from "dotenv";
import { fileURLToPath } from "url";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const API_BASE = process.env.BACKEND_API_BASE_URL || "http://127.0.0.1:8000";
const PORT = Number(process.env.PORT || 3000);
const SESSION_SECRET = process.env.SESSION_SECRET || "dev-secret";

const app = express();

// View engine
app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));

// Body parsers
app.use(express.urlencoded({ extended: true }));

// Session
app.use(
  session({
    secret: SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      sameSite: "lax",
      // secure: true, // enable only if you're serving over HTTPS
      maxAge: 1000 * 60 * 60, // 1 hour
    },
  })
);

// Multer (2MB limit, store in memory)
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 2 * 1024 * 1024 },
});

// Root route: avoid 404 on /
app.get("/", (req, res) => {
  res.redirect("/student/register");
});

// GET form
app.get("/student/register", (req, res) => {
  res.render("student_register", { error: null });
});

// POST form + forward to backend
app.post("/student/register", upload.single("photo"), async (req, res) => {
  console.log(
    "Frontend received /student/register POST, file:",
    req.file ? req.file.originalname : "no file"
  );

  try {
    if (!req.file) {
      return res
        .status(400)
        .render("student_register", { error: "No photo file uploaded" });
    }

    // Build multipart form-data to send to FastAPI backend
    const fd = new FormData();
    const fields = [
      "name",
      "institute",
      "batch",
      "course_name",
      "module",
      "email",
      "password",
    ];

    for (const f of fields) {
      fd.append(f, req.body[f] || "");
    }

    fd.append("photo", req.file.buffer, {
      filename: req.file.originalname,
      contentType: req.file.mimetype,
    });

    const headers = fd.getHeaders();

    const resp = await axios.post(`${API_BASE}/api/students/register`, fd, {
      headers,
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
      timeout: 30000,
    });

    console.log("Backend response:", resp.status, resp.data);
    return res.redirect("/student/login");
  } catch (err) {
    const backendErr = err.response?.data;
    console.error("Error forwarding to backend:", backendErr || err.message);

    const msg =
      backendErr?.detail ||
      backendErr?.message ||
      (typeof backendErr === "string" ? backendErr : null) ||
      "Registration failed";

    return res.status(400).render("student_register", { error: msg });
  }
});

// Simple placeholder login route
app.get("/student/login", (req, res) => {
  res.send("Login page – after registration");
});

// Start server (bind to all interfaces so LAN clients can access)
app.listen(PORT, "0.0.0.0", () => {
  console.log(`Frontend listening on http://0.0.0.0:${PORT}`);
  console.log(`Forwarding backend requests to: ${API_BASE}`);
});
