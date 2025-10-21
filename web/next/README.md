## Next.js App (for Vercel)

Local dev:

```bash
cd web/next
npm install
npm run dev
```

Configure in the page UI:
- Server URL: your tunnel (e.g., `https://<id>.trycloudflare.com`)
- API Key: the key you set for the FastAPI server

Deploy to Vercel:
- Import this `web/next` folder
- No env required (inputs are in-page)


