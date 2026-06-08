FROM node:20-alpine AS build

WORKDIR /app
RUN npm config set registry https://registry.npmmirror.com && npm install -g pnpm

COPY package.json pnpm-lock.yaml ./
RUN pnpm config set registry https://registry.npmmirror.com && pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
