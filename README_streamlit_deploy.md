
# Streamlit Community Cloud Deployment

## 1) Prepare a repo (locally or on GitHub)
Include at minimum:
- `streamlit_app.py`  ← the dashboard app
- `requirements.txt`  ← Python deps

Optionally include a README with screenshots.

## 2) Add Secrets in Streamlit Cloud
In your Streamlit app's **Settings → Secrets**, paste text like:
```toml
MONGO_URI = "mongodb+srv://<user>:<password>@<your-host>/?retryWrites=false&ssl=true"
DB_NAME = "retail"
COLL_NAME = "orders"
```

- For Azure Cosmos DB (Mongo vCore / API for MongoDB), use the connection string from the portal.
- For MongoDB Atlas, use the standard SRV connection string.

## 3) Deploy
- Go to https://streamlit.io/cloud
- Create new app → point to your repo → set the main file to `streamlit_app.py`.
- App will build using `requirements.txt` and read your secrets.

## 4) Import Data (if you haven't already)
Use `mongoimport` from your machine with your connection string:
```bash
mongoimport --uri "$MONGO_URI" \      --db retail --collection orders \      --file retail_orders.jsonl --type json --numInsertionWorkers 4
```

## 5) Share
Streamlit Cloud gives you a public URL you can share. You can also add collaborators.
