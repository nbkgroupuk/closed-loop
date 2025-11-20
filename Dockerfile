FROM nginx:alpine
# clear default site content
RUN rm -rf /usr/share/nginx/html/*
# copy the frontend build (assumes your built static files live in frontend/)
COPY frontend/ /usr/share/nginx/html/
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
