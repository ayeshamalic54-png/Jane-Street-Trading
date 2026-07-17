import os

dashboard_dir = os.path.join(os.path.dirname(__file__), "..", "Street-Trade-Executer", "artifacts", "trading-dashboard", "src", "pages")

config_path = os.path.join(dashboard_dir, "config.tsx")
metrics_path = os.path.join(dashboard_dir, "metrics.tsx")

# 1. Fix config.tsx
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Replace Category type definition
    content = content.replace(
        'type Category = "forex" | "metals" | "crypto" | "stocks" | "custom";',
        'type Category = "forex" | "metals" | "stocks" | "custom";'
    )
    
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("config.tsx Category type updated.")

# 2. Fix metrics.tsx
if os.path.exists(metrics_path):
    with open(metrics_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    target_summary = """  const { data: summary, isLoading: loadingSummary } = useGetMetricsSummary({
    query: { queryKey: getGetMetricsSummaryQueryKey() }
  });"""
  
    replacement_summary = """  const { data: summary, isLoading: loadingSummary } = useGetMetricsSummary(undefined, {
    query: { queryKey: getGetMetricsSummaryQueryKey() }
  });"""
  
    if target_summary in content:
        content = content.replace(target_summary, replacement_summary)
        print("metrics.tsx useGetMetricsSummary call updated.")
    else:
        # Try alternate style
        content = content.replace(
            "useGetMetricsSummary({\n    query: { queryKey: getGetMetricsSummaryQueryKey() }\n  })",
            "useGetMetricsSummary(undefined, {\n    query: { queryKey: getGetMetricsSummaryQueryKey() }\n  })"
        )
        print("metrics.tsx useGetMetricsSummary call updated (fallback).")
        
    with open(metrics_path, "w", encoding="utf-8") as f:
        f.write(content)
