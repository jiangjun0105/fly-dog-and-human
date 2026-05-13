# Digital Drosophila — task runner

# Launch the Streamlit wiki/explorer
wiki:
    uv run streamlit run run_app.py

# Export pre-computed metrics to data/metrics/ (commit these to git)
export:
    uv run python -c "from wiki.metrics import export_metrics; p = export_metrics(); print(f'Exported to {p}')"
