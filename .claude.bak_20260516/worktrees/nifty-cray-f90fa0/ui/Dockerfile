FROM node:20-alpine AS base

# --- Dependencies ---
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- Build ---
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG API_BASE_URL=http://localhost:8000
ENV API_BASE_URL=${API_BASE_URL}
# NEXT_PUBLIC_* vars are inlined at build time by Next.js.
# Pass NEXT_PUBLIC_GATEWAY_URL as a build arg so each deployment target
# (Lovelace: http://192.168.2.101:8008, Turing: leave empty → uses window.location.host fallback)
# bakes the correct WebSocket base URL into the client bundle.
ARG NEXT_PUBLIC_GATEWAY_URL=""
ENV NEXT_PUBLIC_GATEWAY_URL=${NEXT_PUBLIC_GATEWAY_URL}
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- Runtime ---
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
