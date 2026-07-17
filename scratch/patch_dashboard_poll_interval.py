import os

dash_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "dashboard.tsx")

with open(dash_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace refetchInterval to 2000 (2s) instead of 10000 (10s)
old_interval = """  const { data: httpData, isLoading } = useGetDashboard({
    query: {
      refetchInterval: 10000,
      queryKey: getGetDashboardQueryKey(),
    },
  });"""

new_interval = """  const { data: httpData, isLoading } = useGetDashboard({
    query: {
      refetchInterval: 2000,
      queryKey: getGetDashboardQueryKey(),
    },
  });"""

if old_interval in content:
    content = content.replace(old_interval, new_interval)
    print("refetchInterval updated to 2000ms in dashboard.tsx.")
else:
    print("old_interval target not found in dashboard.tsx!")

with open(dash_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
