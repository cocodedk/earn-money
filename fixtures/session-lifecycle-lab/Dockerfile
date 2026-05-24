FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY server.js ./
COPY routes/ ./routes/
EXPOSE 3000
CMD ["node", "server.js"]
