import os

login_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "login.tsx")

with open(login_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the local hardcoded credentials check with the POST fetch call to /api/login
old_submit_fn = """  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (username.trim() === "wasee" && password === "AWais1133@") {
      setIsLoading(true);
      // Simulate authenticating & transition loading exactly like the user's spinner screenshot
      setTimeout(() => {
        localStorage.setItem("wasee_auth", "true");
        onLoginSuccess();
      }, 1200);
    } else {
      setError("Incorrect username or password. Please try again.");
    }
  };"""

new_submit_fn = """  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    })
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json();
          localStorage.setItem("wasee_auth", "true");
          localStorage.setItem("wasee_role", data.role); // "admin" or "user"
          
          // Keep a short transition delay for UX
          setTimeout(() => {
            onLoginSuccess();
          }, 600);
        } else {
          setIsLoading(false);
          const errData = await res.json();
          setError(errData.error || "Incorrect username or password. Please try again.");
        }
      })
      .catch(() => {
        setIsLoading(false);
        setError("Failed to connect to authentication server.");
      });
  };"""

if old_submit_fn in content:
    content = content.replace(old_submit_fn, new_submit_fn)
    print("login.tsx updated to use the api-server auth endpoint.")
else:
    print("old_submit_fn target not found in login.tsx!")

with open(login_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
