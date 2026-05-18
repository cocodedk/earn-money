# Cookbook scanner platform — Vite + React frontend (dev image).
# In production this would be a multi-stage build that emits static
# assets served by nginx; for now we run the Vite dev server with HMR.

FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
