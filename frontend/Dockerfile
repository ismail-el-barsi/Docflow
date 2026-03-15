# Étape 1 : Build de l'application React
FROM node:20-slim AS build-stage
WORKDIR /app

# Installation des dépendances
COPY package*.json ./
RUN npm install

# Copie du code et build
COPY . .
# On s'assure que VITE_API_URL n'est pas utilisé en dur pour privilégier le proxy nginx
RUN npm run build

# Étape 2 : Service des fichiers via Nginx
FROM nginx:stable-alpine AS production-stage

# Copie du build
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copie de la config Nginx personnalisée
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
