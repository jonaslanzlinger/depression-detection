FROM node:18-alpine AS builder

WORKDIR /app
COPY . .
RUN npm install
RUN npm run build -- --configuration production

# Debug: list the output to make sure it exists
RUN ls -la /app/dist/dashboard

FROM nginx:alpine

COPY --from=builder /app/dist/dashboard/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
