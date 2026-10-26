FROM nginx:1.31.7-alpine
# Apply Alpine security fixes released after the upstream image was built.
RUN apk upgrade --no-cache
COPY security-headers.conf /etc/nginx/snippets/churrasplan-security.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/index.html || exit 1
