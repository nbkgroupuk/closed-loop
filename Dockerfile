FROM nginx:alpine

# clear default nginx html
RUN rm -rf /usr/share/nginx/html/*

# copy the built frontend files (assumes index.html is at frontend/index.html
# and any other assets are in frontend/)
COPY frontend/ /usr/share/nginx/html/

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
