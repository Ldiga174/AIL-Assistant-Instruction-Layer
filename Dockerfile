FROM node:22-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM node:22-slim

WORKDIR /app

COPY --from=build /app/node_modules ./node_modules
COPY package.json ./
COPY app.js ./
COPY ailog.md task.todo.json ai.meta.json project.init.md prestart.checklist ./

EXPOSE 8080

USER node

CMD ["node", "app.js"]
