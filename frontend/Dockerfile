# ==============================================================================
# CloudDesk Support Platform — Frontend Next.js Dockerfile (P14-2, CLAUDE.md §15)
# Multi-stage standalone build with node:22-alpine, non-root nextjs user, and healthcheck.
# Build context: frontend directory (e.g. docker build -t clouddesk-frontend frontend/)
# ==============================================================================

# Global argument for reproducible base image pinning
ARG NODE_VERSION=22-alpine

# ------------------------------------------------------------------------------
# Stage 1: Install Dependencies
# ------------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS deps

RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copy dependency manifests
COPY package.json package-lock.json* ./

# Install production and development dependencies needed for building
RUN npm install --ignore-scripts

# ------------------------------------------------------------------------------
# Stage 2: Application Builder
# ------------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Disable Next.js telemetry during container build
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

# Compile Next.js application into standalone output (CLAUDE.md §15)
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 3: Final Production Runtime Image
# ------------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS runner

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

# Install curl for container HEALTHCHECK (CWE-345)
RUN apk add --no-cache curl

# Create dedicated non-root nextjs system user and group (CWE-250)
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy public static assets if present
COPY --from=builder /app/public ./public 2>/dev/null || true

# Copy standalone server build output and static bundles
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Switch to non-root user (CLAUDE.md §13, §15, CWE-250)
USER nextjs

# Expose frontend HTTP port
EXPOSE 3000

# Container liveness health check probing /api/health (CLAUDE.md §15)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

# Production entrypoint starting standalone Next.js server
CMD ["node", "server.js"]
