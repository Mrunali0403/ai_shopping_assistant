# Smart Shopping Assistant

This Streamlit app recommends laptops from the bundled sample catalog in
`data/products.csv`. It filters products and compares prices in Python, then runs
a sequential five-agent CrewAI workflow for requirement extraction, product
search, price comparison, review analysis, and recommendations. The catalog and
reviews are sample data, not live shopping or retailer data.

No model provider or endpoint is selected by default. The application requires
`CREWAI_MODEL`; configure `CREWAI_API_KEY` and `CREWAI_BASE_URL` as required by
your chosen CrewAI-compatible provider. The model identifier must use the format
supported by that provider. Do not commit credentials.

## Local setup (Python 3.12)

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Set the provider configuration in your shell, then start the app:

```sh
export CREWAI_MODEL="<provider>/<model-id>"
export CREWAI_API_KEY="<provider-api-key>"
export CREWAI_BASE_URL="<provider-base-url>"
# Optional; defaults to 0:
export CREWAI_TEMPERATURE="0"
streamlit run app.py
```

Only set the API key and base URL if required by your provider. Keep credentials
out of source control and local environment files.

## Streamlit Community Cloud

Deploy this repository's `main` branch with `app.py` as the app entry point.
Select Python 3.12 in the app's deployment settings. Streamlit installs the
dependencies from `requirements.txt`.

In the app's **Settings > Secrets**, add the provider configuration in TOML
format, using the actual values for your chosen provider:

```toml
CREWAI_MODEL = "provider/model-id"
CREWAI_API_KEY = "your-provider-api-key"
CREWAI_BASE_URL = "https://provider.example/v1"
```

Set only the keys your provider requires; never put real credentials in this
README, source files, or the GitHub repository.