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


class LoggerSetup:
    def __init__(self, save_dir):
        self.logger = self.setup_logger(save_dir)

    def setup_logger(self, save_dir):
        logger = getLogger(__name__)
        logger.setLevel(DEBUG)
        formatter = Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler = StreamHandler()
        stream_handler.setLevel(DEBUG)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        file_handler = FileHandler(f"{save_dir}/log.log")
        file_handler.setLevel(DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        return logger


class DirectoryManager:
    @staticmethod
    def prepare_directory(local_path: str):
        prepare_path = os.path.dirname(local_path)
        if not os.path.exists(prepare_path):
            os.makedirs(prepare_path)


class URLProcessor:
    @staticmethod
    def delete_unnecessary_query(url: str) -> str:
        return re.sub(r"\?ima=\d+", "", url)

    @staticmethod
    def delete_all_query(url: str) -> str:
        return re.sub(r"\?.*", "", url)

    @staticmethod
    def extract_relative_path(url: str) -> str:
        path = url.replace("https://", "").replace("http://", "")
        if path[0] == "/":
            path = path[1:]
        return path

    @staticmethod
    def is_home(url: str) -> bool:
        return "/" == URLProcessor.delete_all_query(url)[-1]

    @staticmethod
    def is_outer_link(base_url: str, url: str) -> bool:
        if url.startswith("http"):
            return not url.startswith(base_url)
        return False

    @staticmethod
    def is_diary_page(url: str) -> bool:
        return "s/s46/diary/detail" in url

    @staticmethod
    def is_blog_list(url: str) -> bool:
        return "s/s46/diary/blog/list" in url

    @staticmethod
    def is_profile(url: str) -> bool:
        return "s/s46/artist" in url

    @staticmethod
    def is_api(url: str) -> bool:
        return not url.endswith("/") and len(url.split("/")[-1].split(".")) == 1

    @staticmethod
    def get_url_from_style(style: str) -> str:
        style = style.replace("\n", "")
        match = re.search(r'url\((.*?)\)', style)
        if match:
            return match.group(1)
        return None


class FileManager:
    @staticmethod
    def save_file(download_url: str, file_local_path: str, logger):
        if os.path.exists(file_local_path):
            logger.warning(f"Skip: '{file_local_path}' already exists.")
        else:
            DirectoryManager.prepare_directory(file_local_path)
            try:
                response = SakuraBlogArchiver.get_response(download_url)
                logger.info(f"Contents save to '{file_local_path}'.")
                with open(file_local_path, "wb") as f:
                    f.write(response.content)
            except requests.exceptions.ConnectionError as e:
                logger.error(e)
                logger.error(f"Failed to download from '{download_url}'.")


class SakuraBlogArchiver:
    def __init__(self):
        self.MODE_ = MODE.BLOG
        self.BLOG_LIST_MAX_PAGE = 8
        self.BLOG_LIST_CURRENT_PAGE = 1
        self.EXEC_DATE_STR = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        self.SAVE_DIR = os.path.join("./output", self.EXEC_DATE_STR) + "/"
        DirectoryManager.prepare_directory(self.SAVE_DIR)
        self.logger = LoggerSetup(self.SAVE_DIR).logger

    @staticmethod
    def get_response(url: str) -> requests.Response:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        time.sleep(random.uniform(1, 2))
        response = requests.get(url, headers=headers)
        return response

    def get_local_path_dir(self, url: str) -> str:
        path = os.path.join(
            self.SAVE_DIR, URLProcessor.extract_relative_path(url))
        if len(path.split("/")[-1].split(".")) > 1:
            path = os.path.dirname(path)
        return path

    def create_relative_path(self, from_: str, to_: str) -> str:
        return os.path.relpath(to_, from_)

    def get_next_page_url(self, soup: BeautifulSoup) -> str:
        next_link = soup.find('a', string="次へ")
        if next_link:
            next_url = next_link.get('href')
            if next_url:
                return next_url
        return None

    def get_next_page_url_blog_list(self, soup: BeautifulSoup) -> str:
        self.BLOG_LIST_CURRENT_PAGE += 1
        next_link = soup.find('a', string=f"{self.BLOG_LIST_CURRENT_PAGE}")
        if next_link:
            next_url = next_link.get('href')
            if next_url:
                return next_url
        return None

    def query_has(self, url: str, query: str) -> bool:
        return query in url

    def replace_tag_url(self, tag, target_html, file_local_path):
        p = None
        if URLProcessor.is_diary_page(URLProcessor.delete_all_query(file_local_path)) or URLProcessor.is_profile(URLProcessor.delete_all_query(file_local_path)) or URLProcessor.is_blog_list(URLProcessor.delete_all_query(file_local_path)):
            p = self.create_relative_path(os.path.dirname(target_html), URLProcessor.delete_unnecessary_query(
                file_local_path)).replace("index.html", "local_index.html")
            tag['href'] = p
        elif tag.name == 'a' or tag.name == 'link':
            p = self.create_relative_path(os.path.dirname(
                target_html), URLProcessor.delete_unnecessary_query(file_local_path))
            tag['href'] = p
        elif tag.name == 'span':
            style = tag['style']
            extracted_url = URLProcessor.get_url_from_style(style)
            p = style.replace(extracted_url, self.create_relative_path(
                os.path.dirname(target_html), URLProcessor.delete_unnecessary_query(file_local_path)))
            tag['style'] = p
        elif tag.name == 'object':
            p = self.create_relative_path(os.path.dirname(
                target_html), URLProcessor.delete_unnecessary_query(file_local_path))
            tag['data'] = p
        else:
            p = self.create_relative_path(os.path.dirname(
                target_html), URLProcessor.delete_unnecessary_query(file_local_path))
            tag['src'] = p
        if p:
            self.logger.info(f"Replace URL to '{p}' in {tag.name} tag.")
        else:
            self.logger.warning(f"Replace URL failed in {tag.name} tag.")

    def save_diary_page(self, url: str) -> str:
        base_url = re.search(r"https?://[^/]+", url).group(0)
        self.logger.info(f"Target URL: {url}")
        response = self.get_response(url)
        self.logger.info(f"status_code: {response.status_code}")

        target_html = self.get_target_html_path(url)
        DirectoryManager.prepare_directory(target_html)
        self.save_response_content(response, target_html)

        soup = BeautifulSoup(response.content, "html.parser")
        next_url = self.get_next_url(soup, base_url)
        self.process_tags(soup, base_url, target_html)

        local_html = target_html.replace("index.html", "local_index.html")
        DirectoryManager.prepare_directory(local_html)
        self.save_local_html(soup, local_html)

        return next_url

    def get_target_html_path(self, url: str) -> str:
        if self.MODE_ == MODE.BLOG_LIST:
            return os.path.join(self.get_local_path_dir(URLProcessor.delete_all_query(url)), str(self.BLOG_LIST_CURRENT_PAGE), "index.html")
        else:
            return os.path.join(self.get_local_path_dir(URLProcessor.delete_all_query(url)), "index.html")

    def save_response_content(self, response: requests.Response, target_html: str):
        with open(target_html, "w") as f:
            f.write(response.text)
        self.logger.info(f"Save to '{target_html}'.")

    def get_next_url(self, soup: BeautifulSoup, base_url: str) -> str:
        next_url = self.get_next_page_url_blog_list(
            soup) if self.MODE_ == MODE.BLOG_LIST else self.get_next_page_url(soup)
        if next_url:
            next_url = base_url + next_url
            self.logger.info(f"Next URL: {next_url}")
        else:
            self.logger.warning("Next URL not found.")
        return next_url

    def process_tags(self, soup: BeautifulSoup, base_url: str, target_html: str):
        tags = soup.find_all(['a', 'link', 'img', 'script',
                             'video', 'audio', 'source', 'object', 'embed', 'span'])
        for tag in tags:
            self.logger.info("-----------")
            download_url = self.get_download_url(tag)
            if download_url is None or URLProcessor.is_outer_link(base_url, download_url):
                self.logger.warning(f"Outer link: {download_url}")
                continue

            if not download_url.startswith("http"):
                download_url = base_url + download_url
            self.logger.info(f"Download from {download_url}")

            file_local_path = self.get_file_local_path(tag, download_url)
            FileManager.save_file(download_url, file_local_path, self.logger)
            self.replace_tag_url(tag, target_html, file_local_path)

    def get_download_url(self, tag) -> str:
        if tag.name == 'span' and 'style' in tag.attrs:
            style = tag['style']
            return URLProcessor.get_url_from_style(style)
        elif tag.name == 'a' or tag.name == 'link':
            return tag.get('href')
        elif tag.name in ['img', 'script', 'video', 'audio', 'source', 'embed']:
            return tag.get('src')
        elif tag.name == 'object':
            return tag.get('data')
        else:
            self.logger.warning(f"Skip: {tag.name}")
            return None

    def get_file_local_path(self, tag, download_url: str) -> str:
        if tag.name == 'a' and URLProcessor.is_blog_list(tag.get('href')):
            if self.query_has(tag.get('href'), "page="):
                page_num = tag.get_text()
                return os.path.join(self.get_local_path_dir(URLProcessor.delete_all_query(download_url)), page_num, "index.html")
            else:
                return os.path.join(self.get_local_path_dir(URLProcessor.delete_all_query(download_url)), "index.html")
        elif URLProcessor.is_api(URLProcessor.delete_all_query(download_url)) or URLProcessor.is_home(URLProcessor.delete_all_query(download_url)):
            return os.path.join(self.get_local_path_dir(URLProcessor.delete_all_query(download_url)), "index.html")
        else:
            return os.path.join(self.get_local_path_dir(URLProcessor.delete_unnecessary_query(download_url)), os.path.basename(URLProcessor.delete_all_query(download_url)))

    def save_local_html(self, soup: BeautifulSoup, local_html: str):
        with open(local_html, "w") as f:
            f.write(soup.prettify())
        self.logger.info(f"Save local HTML to '{local_html}'.")

    def loop(self, url: str):
        start_time = time.time()
        count = 0
        while url:
            lap_time_start = time.time()
            url = self.save_diary_page(url)
            count += 1
            lap_time = time.time() - lap_time_start
            self.logger.info(f"Lap time: {lap_time} [sec]")
        elapsed_time = time.time() - start_time
        self.logger.info(f"Elapsed time: {elapsed_time} [sec]")
        self.logger.info(f"Count: {count}")

    def main(self):
        self.logger.info(f"Save to '{self.SAVE_DIR}' directory.")
        if not os.path.exists(self.SAVE_DIR):
            os.mkdir(self.SAVE_DIR)
        start_time = time.time()

        url = "https://sakurazaka46.com/s/s46/diary/detail/36095?ima=0000&cd=blog"
        self.loop(url)

        url = "https://sakurazaka46.com/s/s46/artist/03?ima=0000"
        self.loop(url)

        url = "https://sakurazaka46.com/s/s46/diary/blog/list?ima=0000&page=0&ct=03&cd=blog"
        self.MODE_ = MODE.BLOG_LIST
        self.loop(url)

        elapsed_time = time.time() - start_time
        self.logger.info(f"Total elapsed time: {elapsed_time} [sec]")


if __name__ == "__main__":
    try:
        archiver = SakuraBlogArchiver()
        archiver.main()
    except Exception as e:
        archiver.logger.error(e)
        raise
