<<<<<<< HEAD
FROM python:3.11-slim

WORKDIR /app
COPY index.html .

EXPOSE 3000
CMD ["python", "-m", "http.server", "3000"]
=======
FROM nginx:alpine

# Copiamo il nostro file index.html nella cartella pubblica di Nginx
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 80
>>>>>>> 9bf39d4eb977f2254ef0b2779bcba3b09f58bb13
