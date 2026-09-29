# Bhoomi AI browser demo

This is a Vite + React frontend configured for static deployment on Vercel. It does not require the Python backend, Postgres, environment variables, or secrets. The app's API-shaped service in `src/services/api.js` runs locally in the browser and saves demo state in `localStorage`.

## Deploy to Vercel

1. Push this repository to GitHub.
2. In Vercel, import the repository and set **Root Directory** to `frontend`.
3. Keep the build command as `npm run build` and output directory as `dist` (also configured in `vercel.json`).
4. Deploy. No environment variables are needed. SPA routes such as `/records` are handled by the included rewrite.

For local development, run `npm install` then `npm run dev` from this directory. `npm run build` creates the deployable `dist` directory.

## Jury walkthrough

The sign-in screen offers six role accounts. Select an account, use the prefilled password `demo`, then sign in. Start with the verification officer or super administrator to see the full workflow. Useful paths: Dashboard → Parcel Intelligence (search `142/2`) → Investigation Center; Document Upload → run the demo pipeline → Verification Queue → review and approve → Land Registry.

Uploads are stored as record metadata in the current browser; source files are not sent to a server. The processing step is simulated and explicitly labelled. Demo data and actions are local to the browser and can be cleared from browser site storage. Do not present demo output as actual OCR or official land decisions.

## Scope

The repository also contains a Python backend and database for the separate full-stack deployment. The Vercel target described here deploys only this frontend. Authentication, OCR, translation, storage, and workflow actions in this static demo are illustrative browser-side behavior, not secure server features.
