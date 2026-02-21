import express from "express";
import { createServer } from "http";
import path from "path";
import { fileURLToPath } from "url";
import cookieParser from "cookie-parser";
import rateLimit from "express-rate-limit";
import helmet from "helmet";
import cors from "cors";
import authRouter from "./auth.ts";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const server = createServer(app);

  // CORS for Netlify frontend
  app.use(cors({
    origin: ['https://pulsen-ai-portal-ems.netlify.app', 'https://pulsenems.solpulsen.se'],
    credentials: true
  }));

  // Security headers (helmet)
  app.use(
    helmet({
      // Strict-Transport-Security: Force HTTPS for 2 years
      hsts: {
        maxAge: 63072000, // 2 years in seconds
        includeSubDomains: true,
        preload: true,
      },
      // Content-Security-Policy: Prevent XSS, clickjacking, code injection
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
          scriptSrc: ["'self'", "'unsafe-inline'"], // unsafe-inline needed for Vite dev
          styleSrc: ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
          fontSrc: ["'self'", "https://fonts.gstatic.com"],
          imgSrc: ["'self'", "data:", "https:"],
          connectSrc: ["'self'", "https://www.elprisetjustnu.se", "https://opendata-download-metfcst.smhi.se"],
          frameSrc: ["'none'"],
          objectSrc: ["'none'"],
          upgradeInsecureRequests: [],
        },
      },
      // X-Frame-Options: Prevent clickjacking
      frameguard: {
        action: "deny",
      },
      // X-Content-Type-Options: Prevent MIME sniffing
      noSniff: true,
      // Referrer-Policy: Control referrer information
      referrerPolicy: {
        policy: "strict-origin-when-cross-origin",
      },
    })
  );

  // Middleware
  app.use(express.json());
  app.use(cookieParser());

  // Rate limiting for auth endpoints (prevent brute force)
  const authLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 20, // limit each IP to 20 requests per windowMs
    message: 'För många inloggningsförsök, försök igen senare',
    standardHeaders: true,
    legacyHeaders: false,
  });

  // Auth routes
  app.use('/api/auth', authLimiter, authRouter);

  // Health check endpoint
  app.get('/api/health', (_req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
  });

  const port = process.env.PORT || 3000;

  server.listen(port, () => {
    console.log(`Server running on http://localhost:${port}/`);
  });
}

startServer().catch(console.error);
