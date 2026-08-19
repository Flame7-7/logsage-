FROM node:20-alpine AS base
 
WORKDIR /app
COPY package.json ./
RUN npm install --legacy-peer-deps
 
COPY . .
 
# Build
FROM base AS builder
RUN npm run build
 
# Production runner
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV production
 
COPY --from=builder /app/public* ./public/
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
 
EXPOSE 3000
CMD ["node", "server.js"]
 