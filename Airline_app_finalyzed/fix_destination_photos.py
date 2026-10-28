from pathlib import Path
import ast
import re
import shutil


ROOT = Path(__file__).resolve().parent

APP_FILE = ROOT / "app.py"

DEST_FILE = (
    ROOT
    / "templates"
    / "destinations.html"
)


# =========================================================
# CHECK FILES
# =========================================================

if not APP_FILE.exists():

    raise SystemExit(
        f"Не найден файл: {APP_FILE}"
    )


if not DEST_FILE.exists():

    raise SystemExit(
        f"Не найден файл: {DEST_FILE}"
    )


app_text = APP_FILE.read_text(
    encoding="utf-8"
)


dest_text = DEST_FILE.read_text(
    encoding="utf-8"
)


# =========================================================
# BACKUPS
# =========================================================

app_backup = (
    ROOT
    / "app_before_destination_photos.py"
)


dest_backup = (
    ROOT
    / "templates"
    / "destinations_before_photos.html"
)


if not app_backup.exists():

    shutil.copy2(
        APP_FILE,
        app_backup
    )


if not dest_backup.exists():

    shutil.copy2(
        DEST_FILE,
        dest_backup
    )


# =========================================================
# IMPORTS FOR APP.PY
# =========================================================

extra_imports = '''

import json

from functools import lru_cache

from urllib.parse import (
    urlencode,
    quote
)

from urllib.request import (
    Request as UrlRequest,
    urlopen
)

from flask import Response
'''


if (
    "from urllib.request "
    "import Request as UrlRequest, urlopen"
    not in app_text
):

    import_marker = (
        "from destination_info "
        "import DESTINATION_INFO"
    )


    if import_marker not in app_text:

        raise SystemExit(
            "В app.py не найден "
            "импорт DESTINATION_INFO."
        )


    app_text = app_text.replace(
        import_marker,
        import_marker
        +
        extra_imports,
        1
    )


# =========================================================
# DESTINATION IMAGE BACKEND
# =========================================================

IMAGE_ROUTE = r'''


# =========================================================
# DESTINATION IMAGES
# =========================================================


@lru_cache(maxsize=128)
def _download_destination_image(
    city,
    country,
    iata_code
):

    """
    Загружает фотографию города
    на стороне Flask.

    Браузер обращается только
    к 127.0.0.1.
    """


    # -----------------------------------------------------
    # WIKIPEDIA PAGE IMAGE
    # -----------------------------------------------------

    def wikipedia_page_thumbnail(
        title
    ):

        params = {

            "action":
                "query",

            "format":
                "json",

            "redirects":
                1,

            "prop":
                "pageimages",

            "piprop":
                "thumbnail",

            "pithumbsize":
                1000,

            "titles":
                title

        }


        api_url = (
            "https://en.wikipedia.org/"
            "w/api.php?"
            +
            urlencode(
                params
            )
        )


        api_request = UrlRequest(

            api_url,

            headers={
                "User-Agent":
                    "AirlineBookingSystem/"
                    "1.0 student-project"
            }

        )


        with urlopen(
            api_request,
            timeout=10
        ) as response:

            data = json.loads(

                response
                .read()
                .decode(
                    "utf-8"
                )

            )


        pages = (
            data
            .get(
                "query",
                {}
            )
            .get(
                "pages",
                {}
            )
        )


        for page in pages.values():

            thumbnail = page.get(
                "thumbnail"
            )


            if (
                thumbnail
                and
                thumbnail.get(
                    "source"
                )
            ):

                return thumbnail[
                    "source"
                ]


        return None


    # -----------------------------------------------------
    # WIKIPEDIA SEARCH
    # -----------------------------------------------------

    def wikipedia_search_thumbnail(
        search_text
    ):

        params = {

            "action":
                "query",

            "format":
                "json",

            "generator":
                "search",

            "gsrsearch":
                search_text,

            "gsrnamespace":
                0,

            "gsrlimit":
                5,

            "prop":
                "pageimages",

            "piprop":
                "thumbnail",

            "pithumbsize":
                1000

        }


        api_url = (
            "https://en.wikipedia.org/"
            "w/api.php?"
            +
            urlencode(
                params
            )
        )


        api_request = UrlRequest(

            api_url,

            headers={
                "User-Agent":
                    "AirlineBookingSystem/"
                    "1.0 student-project"
            }

        )


        with urlopen(
            api_request,
            timeout=10
        ) as response:

            data = json.loads(

                response
                .read()
                .decode(
                    "utf-8"
                )

            )


        pages = (
            data
            .get(
                "query",
                {}
            )
            .get(
                "pages",
                {}
            )
        )


        for page in pages.values():

            thumbnail = page.get(
                "thumbnail"
            )


            if (
                thumbnail
                and
                thumbnail.get(
                    "source"
                )
            ):

                return thumbnail[
                    "source"
                ]


        return None


    # -----------------------------------------------------
    # DOWNLOAD IMAGE
    # -----------------------------------------------------

    def download_image(
        image_url
    ):

        image_request = UrlRequest(

            image_url,

            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "AirlineBookingSystem/1.0"
            }

        )


        with urlopen(
            image_request,
            timeout=15
        ) as image_response:

            image_data = (
                image_response
                .read()
            )


            content_type = (
                image_response
                .headers
                .get_content_type()
            )


        if not content_type.startswith(
            "image/"
        ):

            return None


        return (
            image_data,
            content_type
        )


    # -----------------------------------------------------
    # 1. EXACT CITY PAGE
    # -----------------------------------------------------

    titles = [

        city,

        f"{city}, {country}"

    ]


    for title in titles:

        try:

            image_url = (
                wikipedia_page_thumbnail(
                    title
                )
            )


            if image_url:

                result = download_image(
                    image_url
                )


                if result:

                    return result


        except Exception as error:

            print(

                "WIKIPEDIA PAGE "
                "IMAGE ERROR:",

                city,

                error

            )


    # -----------------------------------------------------
    # 2. WIKIPEDIA SEARCH
    # -----------------------------------------------------

    try:

        image_url = (
            wikipedia_search_thumbnail(
                f"{city} {country} city"
            )
        )


        if image_url:

            result = download_image(
                image_url
            )


            if result:

                return result


    except Exception as error:

        print(

            "WIKIPEDIA SEARCH "
            "IMAGE ERROR:",

            city,

            error

        )


    # -----------------------------------------------------
    # 3. LOREMFLICKR FALLBACK
    # -----------------------------------------------------

    try:

        seed = sum(
            ord(ch)
            for ch
            in iata_code
        )


        fallback_url = (

            "https://loremflickr.com/"
            "1000/650/"
            +
            quote(
                city
            )
            +
            f"?lock={seed}"

        )


        result = download_image(
            fallback_url
        )


        if result:

            return result


    except Exception as error:

        print(

            "LOREMFLICKR "
            "IMAGE ERROR:",

            city,

            error

        )


    return None



# =========================================================
# PLACEHOLDER IF INTERNET IMAGE FAILS
# =========================================================


def _destination_placeholder(
    city,
    iata_code
):

    safe_city = (

        str(city)
        .replace(
            "&",
            "&amp;"
        )
        .replace(
            "<",
            "&lt;"
        )
        .replace(
            ">",
            "&gt;"
        )

    )


    safe_iata = (

        str(iata_code)
        .replace(
            "&",
            "&amp;"
        )
        .replace(
            "<",
            "&lt;"
        )
        .replace(
            ">",
            "&gt;"
        )

    )


    return f"""
    <svg
        xmlns="http://www.w3.org/2000/svg"
        width="1200"
        height="800"
        viewBox="0 0 1200 800"
    >

        <defs>

            <linearGradient
                id="bg"
                x1="0"
                y1="0"
                x2="1"
                y2="1"
            >

                <stop
                    offset="0%"
                    stop-color="#0b2341"
                />

                <stop
                    offset="58%"
                    stop-color="#145b90"
                />

                <stop
                    offset="100%"
                    stop-color="#32a6d2"
                />

            </linearGradient>

        </defs>


        <rect
            width="1200"
            height="800"
            fill="url(#bg)"
        />


        <circle
            cx="970"
            cy="120"
            r="275"
            fill="#67e8f9"
            opacity="0.16"
        />


        <circle
            cx="120"
            cy="90"
            r="150"
            fill="#ffffff"
            opacity="0.05"
        />


        <text
            x="70"
            y="610"
            fill="#ffffff"
            font-family="Arial, sans-serif"
            font-size="78"
            font-weight="700"
        >
            {safe_city}
        </text>


        <text
            x="74"
            y="684"
            fill="#67e8f9"
            font-family="Arial, sans-serif"
            font-size="34"
            font-weight="700"
            letter-spacing="8"
        >
            {safe_iata}
        </text>

    </svg>
    """



# =========================================================
# LOCAL IMAGE URL
# =========================================================


@app.route(
    "/api/destination-image/<iata_code>"
)
def destination_image(
    iata_code
):

    iata_code = (
        iata_code
        .strip()
        .upper()
    )


    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(

                """
                SELECT
                    city,
                    country,
                    iata_code

                FROM airport

                WHERE iata_code = %s;
                """,

                (
                    iata_code,
                )

            )


            airport = (
                cur.fetchone()
            )


    if not airport:

        return Response(

            _destination_placeholder(
                "Destination",
                iata_code
            ),

            mimetype=
                "image/svg+xml"

        )


    try:

        result = (
            _download_destination_image(

                airport[
                    "city"
                ],

                airport[
                    "country"
                ],

                airport[
                    "iata_code"
                ]

            )
        )


        if result:

            (
                image_data,
                content_type
            ) = result


            return Response(

                image_data,

                mimetype=
                    content_type,

                headers={
                    "Cache-Control":
                        "public, "
                        "max-age=86400"
                }

            )


    except Exception as error:

        print(

            "DESTINATION "
            "IMAGE ERROR:",

            airport[
                "iata_code"
            ],

            error

        )


    return Response(

        _destination_placeholder(

            airport[
                "city"
            ],

            airport[
                "iata_code"
            ]

        ),

        mimetype=
            "image/svg+xml",

        headers={
            "Cache-Control":
                "no-cache"
        }

    )

'''


if (
    '@app.route('
    '"/api/destination-image/'
    '<iata_code>")'
    not in app_text
):

    route_marker = (
        '@app.route("/destinations")'
    )


    if route_marker not in app_text:

        raise SystemExit(
            "В app.py не найден "
            '@app.route("/destinations").'
        )


    app_text = app_text.replace(

        route_marker,

        IMAGE_ROUTE
        +
        route_marker,

        1

    )


# =========================================================
# VALIDATE APP.PY
# =========================================================

ast.parse(
    app_text
)


APP_FILE.write_text(
    app_text,
    encoding="utf-8"
)


# =========================================================
# FIX DESTINATIONS.HTML
# =========================================================

new_img = '''<img
                        class="destination-image"
                        src="{{ url_for('destination_image', iata_code=destination.iata_code) }}"
                        alt="{{ destination.city }}, {{ destination.country }}"
                        loading="lazy"
                    >'''


image_pattern = re.compile(

    r'<img\s+class="destination-image[^"]*"'
    r'[\s\S]*?>',

    re.IGNORECASE

)


dest_text, replacements = (
    image_pattern.subn(
        new_img,
        dest_text,
        count=1
    )
)


if replacements != 1:

    raise SystemExit(
        "Не удалось найти "
        "<img> в destinations.html."
    )


DEST_FILE.write_text(
    dest_text,
    encoding="utf-8"
)


# =========================================================
# DONE
# =========================================================

print()

print(
    "=================================="
)

print(
    "ГОТОВО"
)

print(
    "=================================="
)

print()

print(
    "Исправлены:"
)

print(
    "app.py"
)

print(
    "templates/destinations.html"
)

print()

print(
    "Созданы бэкапы:"
)

print(
    "app_before_destination_photos.py"
)

print(
    "templates/"
    "destinations_before_photos.html"
)

print()

print(
    "Теперь запусти:"
)

print()

print(
    "python app.py"
)

print()

print(
    "Проверка картинки Алматы:"
)

print(
    "http://127.0.0.1:5000/"
    "api/destination-image/ALA"
)

print()

print(
    "Страница направлений:"
)

print(
    "http://127.0.0.1:5000/"
    "destinations"
)

print()