import { Router, Request, Response } from 'express';
import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';

const router = Router();

// JWT secret - in production, use environment variable
const JWT_SECRET = process.env.JWT_SECRET || 'pulsen-ai-secret-key-change-in-production';
const JWT_EXPIRES_IN = '24h';

// User database (in production, use a real database)
// Password hashed with bcrypt: pulsen2026
const USERS = [
  {
    username: 'admin',
    // bcrypt hash of "pulsen2026"
    passwordHash: '$2b$10$.au7qaivZNPpvnpDcxebju1/4B5BxxBhK096rb.hBB8I4a9VVvy2C',
    role: 'Admin',
    email: 'admin@solpulsen.se'
  }
];

// Helper to generate password hash (for creating new users)
export async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, 10);
}

// Login endpoint
router.post('/login', async (req: Request, res: Response) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({ error: 'Användarnamn och lösenord krävs' });
    }

    // Find user
    const user = USERS.find(u => u.username === username);
    if (!user) {
      return res.status(401).json({ error: 'Felaktigt användarnamn eller lösenord' });
    }

    // Verify password
    const validPassword = await bcrypt.compare(password, user.passwordHash);
    if (!validPassword) {
      return res.status(401).json({ error: 'Felaktigt användarnamn eller lösenord' });
    }

    // Generate JWT
    const token = jwt.sign(
      { username: user.username, role: user.role },
      JWT_SECRET,
      { expiresIn: JWT_EXPIRES_IN }
    );

    // Set httpOnly cookie
    res.cookie('pulsen_auth_token', token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 24 * 60 * 60 * 1000, // 24 hours
    });

    // Return user info (no password)
    res.json({
      user: username,
      role: user.role,
      loginTime: Date.now(),
    });
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Serverfel vid inloggning' });
  }
});

// Verify endpoint (check if user is authenticated)
router.get('/verify', (req: Request, res: Response) => {
  try {
    const token = req.cookies?.pulsen_auth_token;

    if (!token) {
      return res.status(401).json({ error: 'Inte autentiserad' });
    }

    // Verify JWT
    const decoded = jwt.verify(token, JWT_SECRET) as { username: string; role: string };

    res.json({
      user: decoded.username,
      role: decoded.role,
      loginTime: Date.now(), // Could store this in JWT if needed
    });
  } catch (error) {
    res.status(401).json({ error: 'Ogiltig session' });
  }
});

// Logout endpoint
router.post('/logout', (_req: Request, res: Response) => {
  res.clearCookie('pulsen_auth_token');
  res.json({ success: true });
});

export default router;
