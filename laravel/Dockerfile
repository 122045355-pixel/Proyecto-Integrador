FROM php:8.4-fpm-alpine

RUN apk add --no-cache oniguruma-dev libxml2-dev libzip-dev zip unzip curl git bash \
    && docker-php-ext-install pdo pdo_mysql mbstring exif pcntl bcmath zip

RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

WORKDIR /var/www/html

COPY . /var/www/html

RUN composer install --no-interaction --prefer-dist

EXPOSE 8000

CMD ["php", "artisan", "serve", "--host=0.0.0.0", "--port=8000"]