FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./

RUN npm ci --include=dev || npm install

COPY . .

ARG VITE_ENABLE_DEV_LOGIN=false
ENV VITE_ENABLE_DEV_LOGIN=$VITE_ENABLE_DEV_LOGIN

RUN chmod +x node_modules/.bin/vite && npm run build
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80