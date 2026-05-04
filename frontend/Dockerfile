FROM node:18-alpine AS build

ARG REACT_APP_API_URL=/api
ARG REACT_APP_SENTRY_DSN=
ARG REACT_APP_SENTRY_ENV=production
ARG REACT_APP_SENTRY_TRACES_RATE=0.1

ENV REACT_APP_API_URL=$REACT_APP_API_URL \
    REACT_APP_SENTRY_DSN=$REACT_APP_SENTRY_DSN \
    REACT_APP_SENTRY_ENV=$REACT_APP_SENTRY_ENV \
    REACT_APP_SENTRY_TRACES_RATE=$REACT_APP_SENTRY_TRACES_RATE

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80
