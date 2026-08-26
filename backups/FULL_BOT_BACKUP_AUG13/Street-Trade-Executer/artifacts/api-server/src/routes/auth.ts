import { Router } from "express";
import { db } from "@workspace/db";
import { botStateTable } from "@workspace/db";
import { eq } from "drizzle-orm";

const router = Router();

router.post("/login", async (req, res) => {
  try {
    const { username, password } = req.body;
    const botState = await db.select().from(botStateTable).where(eq(botStateTable.id, 1)).limit(1).then(r => r[0]);
    
    // Check user role credentials dynamically
    const userPass = botState?.userPassword ?? "user123";
    if (username?.toLowerCase() === "user" && password === userPass) {
      return res.json({ success: true, role: "user" });
    }

    const adminUser = botState?.adminUsername ?? "wasee";
    const adminPass = botState?.adminPassword ?? "AWais1133@";

    if (username === adminUser && password === adminPass) {
      return res.json({ success: true, role: "admin" });
    }
    return res.status(401).json({ error: "Incorrect username or password" });
  } catch (err) {
    req.log.error({ err }, "Login error");
    return res.status(500).json({ error: "Login error" });
  }
});

router.post("/config/password", async (req, res) => {
  try {
    const { currentPassword, newPassword } = req.body;
    const botState = await db.select().from(botStateTable).where(eq(botStateTable.id, 1)).limit(1).then(r => r[0]);
    const adminPass = botState?.adminPassword ?? "AWais1133@";

    if (currentPassword !== adminPass) {
      return res.status(400).json({ error: "Current password is incorrect" });
    }
    await db.update(botStateTable).set({ adminPassword: newPassword }).where(eq(botStateTable.id, 1));
    return res.json({ success: true });
  } catch (err) {
    req.log.error({ err }, "Password change error");
    return res.status(500).json({ error: "Password change error" });
  }
});

// Admin endpoint to change user's password
router.post("/config/user-password", async (req, res) => {
  try {
    const { newUserPassword } = req.body;
    await db.update(botStateTable).set({ userPassword: newUserPassword }).where(eq(botStateTable.id, 1));
    return res.json({ success: true });
  } catch (err) {
    req.log.error({ err }, "User password change error");
    return res.status(500).json({ error: "User password change error" });
  }
});

export default router;
