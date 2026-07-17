import os

metrics_path = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages", "metrics.tsx")

with open(metrics_path, "r", encoding="utf-8") as f:
    content = f.read()

# Restore 1-argument call
target = """  const { data: summary, isLoading: loadingSummary } = useGetMetricsSummary(undefined, {
    query: { queryKey: getGetMetricsSummaryQueryKey() }
  });"""

replacement = """  const { data: summary, isLoading: loadingSummary } = useGetMetricsSummary({
    query: { queryKey: getGetMetricsSummaryQueryKey() }
  });"""

if target in content:
    content = content.replace(target, replacement)
    print("metrics.tsx useGetMetricsSummary call restored to 1-argument signature.")
else:
    # Try alternate style
    content = content.replace(
        "useGetMetricsSummary(undefined, {\n    query: { queryKey: getGetMetricsSummaryQueryKey() }\n  })",
        "useGetMetricsSummary({\n    query: { queryKey: getGetMetricsSummaryQueryKey() }\n  })"
    )
    print("metrics.tsx useGetMetricsSummary call restored (fallback).")

with open(metrics_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File updated.")
