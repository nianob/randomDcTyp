import https from "https";
import fs from "fs";
import express from "express";
import session from "express-session"
import SQLiteStoreFactory from "connect-sqlite3";
import path from "path";
import { fileURLToPath } from "url";
import dotenv from "dotenv";
import qs from "querystring";


async function refresh_token(req) {
    const body = qs.stringify({
        client_id: process.env.CLIENT_ID,
        client_secret: process.env.CLIENT_SECRET,
        grant_type: "refresh_token",
        refresh_token: req.session.discord.refresh_token
    });

    const dres = await fetch("https://discord.com/api/oauth2/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body
    });

    const data = await dres.json();

    req.session.discord = {
        access_token: data.access_token,
        token_type: data.token_type,
        refresh_token: data.refresh_token ?? req.session.discord.refresh_token,
        expires_at: Date.now() + data.expires_in * 1000
    };
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config();
const app = express();

const SQLiteStore = SQLiteStoreFactory(session);
app.use(session({
    store: new SQLiteStore({
        db: "sessions.sqlite",
        dir: "./data",
        ttl: 60 * 60 * 24 * 30
    }),
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: {
      httpOnly: true,
      secure: true,       // REQUIRED for Discord Activities
      sameSite: "none",   // REQUIRED inside Discord iframe
      maxAge: 1000 * 60 * 60 * 24 * 30 // 30 days
    }
}));

app.use(express.json());

// ---- CORS (important for Discord iframe) ----
app.use((req, res, next) => {
    res.header("Access-Control-Allow-Origin", "https://discordsays.com");
    res.header("Access-Control-Allow-Credentials", "true");
    res.header("Access-Control-Allow-Headers", "Content-Type");
    next();
});

// ---- Static files ----
app.use("/", express.static(path.join(__dirname, "public")));

// ---- API ----
app.get("/api/config", (req, res) => {
    res.json({
        oauth: process.env.OAUTH2_LINK,
        bot_id: process.env.CLIENT_ID
    })
});

app.post("/api/auth", async (req, res) => {
    const { code } = req.body

    if (!code) return res.status(400).json({ error: "Missing Code"});

    const body = qs.stringify({
        client_id: process.env.CLIENT_ID,
        client_secret: process.env.CLIENT_SECRET,
        grant_type: "authorization_code",
        code,
        redirect_uri: "https://localhost:3030/OAuth2.html" // This must match the url of the server or discord will return invalid redirect uri; Automate changing this at some point
    })

    try {
        const tokenRes = await fetch("https://discord.com/api/oauth2/token", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body
        });

        // data = {access_token, token_type, expores_in, refresh_token, scope }
        const data = await tokenRes.json()

        // Store the tokens for autologin
        const expiresAt = Date.now() + data.expires_in * 1000;

        req.session.discord = {
            access_token: data.access_token,
            token_type: data.token_type,
            refresh_token: data.refresh_token,
            expires_at: expiresAt
        };

        res.json({ ok: true });
    } catch (err) {
        console.log(err);
        res.status(500).json({ error: "Token exchange failed" })
    }
});

app.get("/api/me", async (req, res) => {
    if (!req.session?.discord) {
        return res.json({ logged_in: false })
    }
    if (Date.now() > req.session.discord.expires_at - 60 * 1000) { // Access token invalid (60 second safety margin)
        try {
            await refresh_token(req);
        } catch {
            return res.json({ logged_in: false })
        }
    }

    try {
        const userRes = await fetch("https://discord.com/api/users/@me", {
            headers: {
                Authorization: `${req.session.discord.token_type} ${req.session.discord.access_token}`
            }
        })

        let user = await userRes.json();

        if (!user.id) { // assume 401 unauthorized
            try {
                await refresh_token(req);
            } catch {
                return res.json({ logged_in: false })
            }
            const userRes = await fetch("https://discord.com/api/users/@me", {
                headers: {
                    Authorization: `${req.session.discord.token_type} ${req.session.discord.access_token}`
                }
            })
            user = await userRes.json();
        }

        return res.json({
            logged_in: true,
            ok: !!user.id,
            user: {
                id: user.id,
                username: user.username,
                avatar: user.avatar
            }
        })
    } catch {
        return res.status(500).json({
            logged_in: true,
            error: "Unable to read userdata"
        })
    }
});

// ---- Start server ----
https.createServer(
    {
        key: fs.readFileSync("localhost-key.pem"), // The server will be http and acessed by Apache in prod
        cert: fs.readFileSync("localhost.pem"),    // so this will be removed
    },
    app
).listen(3000);
