# Stage 1: build Angular app
FROM node:18 AS build

WORKDIR /app

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .
RUN npm run build --configuration=production

# Stage 2: serve using NGINX
FROM nginx:alpine

COPY --from=build /app/dist/dashboard /usr/share/nginx/html


EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
