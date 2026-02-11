FROM nginx:alpine
# clear default site content
RUN rm -rf /usr/share/nginx/html/*
COPY frontend/ /usr/share/nginx/html/
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
