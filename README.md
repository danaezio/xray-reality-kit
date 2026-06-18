# Xray Reality Kit

Готовый установщик для быстрого разворачивания личного VPN на Ubuntu VPS.

Что ставится:

- Xray
- VLESS
- REALITY
- XHTTP transport
- BBR-настройки скорости
- UFW firewall
- минимальная веб-панель для создания и удаления ключей

По умолчанию используется рабочая связка:

```text
VLESS + REALITY + XHTTP
Port: 443
SNI/target: www.cloudflare.com
XHTTP path: /xray-cloud
GUI panel: 8765
```

## Быстрый старт на новом VPS

Подключись к серверу:

```bash
ssh root@IP_ТВОЕГО_VPS
```

Установи Git:

```bash
apt update
apt install -y git
```

Склонируй репозиторий:

```bash
git clone git@github.com:danaezio/xray-reality-kit.git
cd xray-reality-kit
```

Если на VPS еще не настроен SSH-доступ к GitHub, используй HTTPS:

```bash
git clone https://github.com/danaezio/xray-reality-kit.git
cd xray-reality-kit
```

Запусти установку:

```bash
bash scripts/install.sh --host IP_ТВОЕГО_VPS --panel-public
```

Пример:

```bash
bash scripts/install.sh --host 123.123.123.123 --panel-public
```

В конце установщик покажет:

- готовую VLESS-ссылку для импорта в клиент
- токен от панели
- адрес панели

## Вход в панель

Если установка была с `--panel-public`, открой в браузере:

```text
http://IP_ТВОЕГО_VPS:8765
```

Токен можно посмотреть на сервере:

```bash
grep PANEL_TOKEN /etc/xray-key-panel.env
```

В панели можно:

- создавать новые ключи
- удалять ключи
- копировать VLESS-ссылки
- перезапускать Xray

## Более безопасный вход в панель

Публичный режим `--panel-public` удобный, но панель открыта в интернет на отдельном порту. Она защищена токеном, но это все равно обычный HTTP.

Более безопасный вариант: ставить без `--panel-public`.

```bash
bash scripts/install.sh --host IP_ТВОЕГО_VPS
```

Потом открывать панель через SSH-туннель:

```bash
ssh -L 8765:127.0.0.1:8765 root@IP_ТВОЕГО_VPS
```

И открыть на своем компьютере:

```text
http://127.0.0.1:8765
```

## Если Xray уже установлен

Если на сервере уже есть файл:

```text
/usr/local/etc/xray/config.json
```

установщик остановится, чтобы случайно ничего не перезаписать.

Чтобы заменить существующий конфиг, используй `--force`:

```bash
bash scripts/install.sh --host IP_ТВОЕГО_VPS --panel-public --force
```

Старый конфиг будет сохранен рядом с именем вида:

```text
/usr/local/etc/xray/config.json.backup-YYYYMMDD-HHMMSS
```

## Установка с доменом

Если у тебя есть домен или поддомен, направь `A`-запись на IP сервера, затем запусти:

```bash
bash scripts/install.sh --host vpn.example.com --panel-public
```

В VLESS-ссылках будет использоваться домен вместо IP.

## Полезные команды

Проверить Xray:

```bash
systemctl status xray --no-pager
```

Проверить панель:

```bash
systemctl status xray-key-panel --no-pager
```

Посмотреть логи Xray:

```bash
journalctl -u xray -n 80 --no-pager
```

Посмотреть логи панели:

```bash
journalctl -u xray-key-panel -n 80 --no-pager
```

Перезапустить Xray:

```bash
systemctl restart xray
```

Перезапустить панель:

```bash
systemctl restart xray-key-panel
```

Посмотреть токен панели:

```bash
grep PANEL_TOKEN /etc/xray-key-panel.env
```

## Обновить репозиторий на VPS

В папке проекта:

```bash
git pull
```

Если нужно обновить только веб-панель без изменения VPN-конфига:

```bash
bash scripts/install-panel.sh
systemctl restart xray-key-panel
```

## Параметры установщика

```text
--host VALUE      IP или домен VPS для VLESS-ссылок
--sni VALUE       REALITY target/SNI, по умолчанию www.cloudflare.com
--path VALUE      XHTTP path, по умолчанию /xray-cloud
--client VALUE    имя первого клиента, по умолчанию main
--panel-public    открыть панель в интернет на порту 8765
--force           заменить существующий Xray config после backup
```

Пример с кастомным именем клиента:

```bash
bash scripts/install.sh \
  --host IP_ТВОЕГО_VPS \
  --client iphone-main \
  --panel-public
```

## Что где лежит

```text
/usr/local/etc/xray/config.json
```

Основной конфиг Xray.

```text
/usr/local/etc/xray/key-panel-settings.json
```

Настройки генерации ссылок для панели.

```text
/etc/xray-key-panel.env
```

Настройки панели и токен доступа.

```text
/opt/xray-key-panel/app.py
```

Файл веб-панели.

## Важное замечание

Не ставь обычный HTTPS reverse proxy на порт `443` без отдельной настройки маршрутизации, потому что порт `443` уже использует Xray Reality.

Если нужна красивая HTTPS-панель на домене, лучше делать это отдельным шагом через SNI-routing или другой порт, чтобы не сломать VPN.
