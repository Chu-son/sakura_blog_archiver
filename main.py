import requests
from bs4 import BeautifulSoup
import os
import datetime
import re
import time
import random

from logging import getLogger, FileHandler, StreamHandler, Formatter, DEBUG

import enum


class MODE(enum.Enum):
    BLOG = "blog"
    PROFILE = "profile"
    BLOG_LIST = "blog_list"


MODE_ = MODE.BLOG

BLOG_LIST_MAX_PAGE = 8
BLOG_LIST_CURRENT_PAGE = 1


def prepare_directory(local_path: str):
    prepare_path = os.path.dirname(local_path)
    if not os.path.exists(prepare_path):
        logger.info(f"Create directory '{prepare_path}'.")
        os.makedirs(prepare_path)
    else:
        logger.info(f"Directory '{prepare_path}' already exists.")


EXEC_DATE_STR = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

# logger
logger = getLogger(__name__)
logger.setLevel(DEBUG)

formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# stream handler
stream_handler = StreamHandler()
stream_handler.setLevel(DEBUG)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

SAVE_DIR = os.path.join("./output", EXEC_DATE_STR)
SAVE_DIR += "/"
prepare_directory(SAVE_DIR)

# file handler
file_handler = FileHandler(f"{SAVE_DIR}/log.log")
file_handler.setLevel(DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def delete_unnecessary_query(url: str) -> str:
    return re.sub(r"\?ima=\d+", "", url)


def delete_all_query(url: str) -> str:
    return re.sub(r"\?.*", "", url)


def extract_relative_path(url: str) -> str:
    # Extract path from URL
    # path = re.sub(r"https?://", "", url)
    path = url.replace("https://", "")
    path = path.replace("http://", "")

    if path[0] == "/":
        path = path[1:]

    # Remove query parameters from path
    # path = re.sub(r"\?.*", "", path)
    return path


def get_local_path_dir(url: str) -> str:
    path = os.path.join(SAVE_DIR, extract_relative_path(url))
    if len(path.split("/")[-1].split(".")) > 1:
        path = os.path.dirname(path)
    return path


def is_home(url: str) -> bool:
    return "/" == delete_all_query(url)[-1]


def is_outer_link(base_url: str, url: str) -> bool:
    if url.startswith("http"):
        return not url.startswith(base_url)
    return False


def is_diary_page(url: str) -> bool:
    return "s/s46/diary/detail" in url


def is_blog_list(url: str) -> bool:
    return "s/s46/diary/blog/list" in url

def is_profile(url: str) -> bool:
    return "s/s46/artist" in url


def is_api(url: str) -> bool:
    # パスの末尾が"/"ではなく、拡張子がない場合はAPIとみなす
    return not url.endswith("/") and len(url.split("/")[-1].split(".")) == 1


def get_url_from_style(style: str) -> str:
    logger.info(f"style: {style}")
    style = style.replace("\n", "")
    match = re.search(r'url\((.*?)\)', style)
    if match:
        return match.group(1)
    return None


def get_response(url: str) -> requests.Response:
    # agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    time.sleep(random.uniform(1, 2))
    response = requests.get(url, headers=headers)
    logger.info(f"status_code: {response.status_code}")
    return response


def create_relative_path(from_: str, to_: str) -> str:
    return os.path.relpath(to_, from_)


def get_next_page_url(soup: BeautifulSoup) -> str:
    # aタグでContentsが"次へ"のリンクを取得
    next_link = soup.find('a', string="次へ")
    if next_link:
        next_url = next_link.get('href')
        if next_url:
            return next_url
    return None


def get_next_page_url_blog_list(soup: BeautifulSoup) -> str:
    global BLOG_LIST_CURRENT_PAGE
    BLOG_LIST_CURRENT_PAGE += 1

    # aタグでContentsが"次へ"のリンクを取得
    next_link = soup.find('a', string=f"{BLOG_LIST_CURRENT_PAGE}")
    if next_link:
        next_url = next_link.get('href')
        if next_url:
            return next_url
    return None


def query_has(url: str, query: str) -> bool:
    return query in url


def save_diary_page(url: str) -> str:

    # base url extract from url
    base_url = re.search(r"https?://[^/]+", url).group(0)

    logger.info(f"Target URL: {url}")
    response = get_response(url)
    logger.info(f"status_code: {response.status_code}")

    if MODE_ == MODE.BLOG_LIST:
        target_html = os.path.join(get_local_path_dir(
            delete_all_query(url)
        ),
            str(BLOG_LIST_CURRENT_PAGE),
            "index.html")
    else:
        target_html = os.path.join(get_local_path_dir(
            delete_all_query(url)
        ), "index.html")
    prepare_directory(target_html)
    with open(target_html, "w") as f:
        f.write(response.text)
    logger.info(f"Save to '{target_html}'.")

    soup = BeautifulSoup(response.content, "html.parser")

    if MODE_ == MODE.BLOG_LIST:
        next_url = get_next_page_url_blog_list(soup)
    else:
        # aタグでContentsが"次へ"のリンクを取得
        next_url = get_next_page_url(soup)

    if next_url:
        next_url = base_url + next_url
        logger.info(f"Next URL: {next_url}")
    else:
        logger.warning("Next URL not found.")

    # リンク、画像、動画、CSS、JavaScript、音声、埋め込みオブジェクトのタグを列挙
    tags = soup.find_all(['a', 'link', 'img', 'script',
                         'video', 'audio', 'source', 'object', 'embed', 'span'])

    for tag in tags:
        logger.info("-----------")

        download_url = None
        if tag.name == 'span' and 'style' in tag.attrs:
            style = tag['style']
            download_url = get_url_from_style(style)
        elif tag.name == 'a' or tag.name == 'link':
            download_url = tag.get('href')
        elif tag.name in ['img', 'script', 'video', 'audio', 'source', 'embed']:
            download_url = tag.get('src')
        elif tag.name == 'object':
            download_url = tag.get('data')
        else:
            logger.warning(f"Skip: {tag.name}")
            continue

        logger.info(f"tag: {tag.name}, download_url: {download_url}")

        if download_url is None:
            continue
        if is_outer_link(base_url, download_url):
            logger.warning(f"Outer link: {download_url}")
            continue

        # Relative path to absolute path
        if not download_url.startswith("http"):
            download_url = base_url + download_url
        logger.info(f"Download from {download_url}")

        # ファイルを保存
        if tag.name == 'a' and is_blog_list(tag.get('href')):
            if query_has(tag.get('href'), "page="):
                page_num = tag.get_text()

                file_local_path = os.path.join(get_local_path_dir(
                    delete_all_query(download_url)), page_num, "index.html")
            else:
                file_local_path = os.path.join(get_local_path_dir(
                    delete_all_query(download_url)), "index.html")
            
        # if MODE_ == MODE.BLOG_LIST and tag.name == 'a' and query_has(tag.get('href'), "page=") and is_blog_list(tag.get('href')):
            # num from tag contents
            # page_num = tag.get_text()

            # file_local_path = os.path.join(get_local_path_dir(
            #     delete_all_query(download_url)), page_num, "index.html")

        elif is_api(delete_all_query(download_url)):
            file_local_path = os.path.join(get_local_path_dir(
                delete_all_query(download_url)), "index.html")
        elif is_home(delete_all_query(download_url)):
            file_local_path = os.path.join(get_local_path_dir(
                delete_all_query(download_url)), "index.html")
        else:
            file_local_path = os.path.join(get_local_path_dir(delete_unnecessary_query(download_url)),
                                           os.path.basename(delete_all_query(download_url)))

        if os.path.exists(file_local_path):
            logger.warning(f"Skip: '{file_local_path}' already exists.")
        else:
            prepare_directory(file_local_path)

            try:
                response = get_response(download_url)

                logger.info(f"Contents save to '{file_local_path}'.")
                with open(file_local_path, "wb") as f:
                    f.write(response.content)
            except requests.exceptions.ConnectionError as e:
                logger.error(e)
                logger.error(f"Failed to download from '{download_url}'.")
                continue

        # ファイル名をローカルパスに置換
        p = None
        # if MODE_ == MODE.BLOG_LIST and tag.name == 'a' and query_has(tag.get('href'), "page=") and is_blog_list(tag.get('href')):
        #     p = create_relative_path(os.path.dirname(
        #         target_html), delete_unnecessary_query(file_local_path)).replace("index.html", "local_index.html")
        #     tag['href'] = p
        if is_diary_page(delete_all_query(download_url)) or is_profile(delete_all_query(download_url)) or is_blog_list(delete_all_query(download_url)):
            p = create_relative_path(os.path.dirname(
                target_html), delete_unnecessary_query(file_local_path)).replace("index.html", "local_index.html")
            tag['href'] = p
        elif tag.name == 'a' or tag.name == 'link':
            p = create_relative_path(os.path.dirname(
                target_html), delete_unnecessary_query(file_local_path))
            tag['href'] = p
        elif tag.name == 'span':
            style = tag['style']
            extracted_url = get_url_from_style(style)
            p = style.replace(extracted_url, create_relative_path(
                os.path.dirname(target_html), delete_unnecessary_query(file_local_path)))
            tag['style'] = p
        elif tag.name == 'object':
            p = create_relative_path(os.path.dirname(
                target_html), delete_unnecessary_query(file_local_path))
            tag['data'] = p
        else:
            p = create_relative_path(os.path.dirname(
                target_html), delete_unnecessary_query(file_local_path))
            tag['src'] = p
        if p:
            logger.info(f"Replace URL to '{p}' in {tag.name} tag.")
        else:
            logger.warning(f"Replace URL failed in {tag.name} tag.")

    logger.info("-----------")
    # HTMLを保存

    # if MODE_ == MODE.BLOG_LIST:
    #     local_html = os.path.join(get_local_path_dir(
    #         delete_all_query(url)
    #     ),
    #         str(BLOG_LIST_CURRENT_PAGE-1),
    #         "local_index.html")
    # else:
    #     local_html = os.path.join(get_local_path_dir(
    #         delete_all_query(url)
    #     ), "local_index.html")
    local_html = target_html.replace("index.html", "local_index.html")
    prepare_directory(local_html)
    with open(local_html, "w") as f:
        f.write(soup.prettify())
    logger.info(f"Save local HTML to '{local_html}'.")

    return next_url


def loop(url: str):
    start_time = time.time()
    count = 0
    while url:
        lap_time_start = time.time()
        url = save_diary_page(url)
        count += 1
        lap_time = time.time() - lap_time_start
        logger.info(f"Lap time: {lap_time} [sec]")

    elapsed_time = time.time() - start_time
    logger.info(f"Elapsed time: {elapsed_time} [sec]")
    logger.info(f"Count: {count}")

def main():
    global MODE_

    logger.info(f"Save to '{SAVE_DIR}' directory.")
    if not os.path.exists(SAVE_DIR):
        os.mkdir(SAVE_DIR)

    start_time = time.time()

    # blog -----
    # first
    url = "https://sakurazaka46.com/s/s46/diary/detail/36136?ima=0000&cd=blog"

    # blog 3rd from the end
    # url = "https://sakurazaka46.com/s/s46/diary/detail/54377?ima=0000&cd=blog"

    # blog resume
    # url = "https://sakurazaka46.com/s/s46/diary/detail/45825?ima=0000&cd=blog"
    # url = "https://sakurazaka46.com/s/s46/diary/detail/50422?ima=0000&cd=blog"

    loop(url)

    # DONE
    # profile ~~~~~
    url = "https://sakurazaka46.com/s/s46/artist/07?ima=0000"

    loop(url)

    # DONE
    # blog list -----
    url = "https://sakurazaka46.com/s/s46/diary/blog/list?ima=0000&page=0&ct=07&cd=blog"
    # blog list 6th page
    # url = "https://sakurazaka46.com/s/s46/diary/blog/list?ima=0000&page=6&ct=07&cd=blog"
    # global BLOG_LIST_CURRENT_PAGE
    # BLOG_LIST_CURRENT_PAGE = 7
    MODE_ = MODE.BLOG_LIST
    loop(url)

    elapsed_time = time.time() - start_time
    logger.info(f"Total elapsed time: {elapsed_time} [sec]")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(e)
        raise
