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
    def __init__(self, log_dir):
        self.logger = self.setup_logger(log_dir)

    def setup_logger(self, log_dir):
        logger = getLogger(__name__)
        logger.setLevel(DEBUG)
        formatter = Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler = StreamHandler()
        stream_handler.setLevel(DEBUG)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        file_handler = FileHandler(f"{log_dir}/log.log")
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
    def remove_query(url: str) -> str:
        return re.sub(r"\?ima=\d+", "", url)

    @staticmethod
    def remove_all_query(url: str) -> str:
        return re.sub(r"\?.*", "", url)

    @staticmethod
    def get_relative_path(url: str) -> str:
        path = url.replace("https://", "").replace("http://", "")
        if path[0] == "/":
            path = path[1:]
        return path

    @staticmethod
    def is_home_page(url: str) -> bool:
        return "/" == URLProcessor.remove_all_query(url)[-1]

    @staticmethod
    def is_external_link(base_url: str, url: str) -> bool:
        if url.startswith("http"):
            return not url.startswith(base_url)
        return False

    @staticmethod
    def is_diary_page(url: str) -> bool:
        return "s/s46/diary/detail" in url

    @staticmethod
    def is_blog_list_page(url: str) -> bool:
        return "s/s46/diary/blog/list" in url

    @staticmethod
    def is_profile_page(url: str) -> bool:
        return "s/s46/artist" in url

    @staticmethod
    def is_api_endpoint(url: str) -> bool:
        return not url.endswith("/") and len(url.split("/")[-1].split(".")) == 1

    @staticmethod
    def extract_url_from_style(style: str) -> str:
        style = style.replace("\n", "")
        match = re.search(r'url\((.*?)\)', style)
        if match:
            return match.group(1)
        return None


class FileManager:
    @staticmethod
    def save_file(download_url: str, local_path: str, logger):
        if os.path.exists(local_path):
            logger.warning(f"Skip: '{local_path}' already exists.")
        else:
            DirectoryManager.prepare_directory(local_path)
            try:
                response = SakuraBlogArchiver.fetch_response(download_url)
                logger.info(f"Contents saved to '{local_path}'.")
                with open(local_path, "wb") as f:
                    f.write(response.content)
            except requests.exceptions.ConnectionError as e:
                logger.error(e)
                logger.error(f"Failed to download from '{download_url}'.")


class SakuraBlogArchiver:
    def __init__(self):
        self.mode = MODE.BLOG
        self.max_blog_list_page = 8
        self.current_blog_list_page = 1
        self.execution_date_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        self.save_dir = os.path.join("./output", self.execution_date_str) + "/"
        DirectoryManager.prepare_directory(self.save_dir)
        self.logger = LoggerSetup(self.save_dir).logger

    @staticmethod
    def fetch_response(url: str) -> requests.Response:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        time.sleep(random.uniform(1, 2))
        response = requests.get(url, headers=headers)
        return response

    def get_local_directory(self, url: str) -> str:
        path = os.path.join(self.save_dir, URLProcessor.get_relative_path(url))
        if len(path.split("/")[-1].split(".")) > 1:
            path = os.path.dirname(path)
        return path

    def create_relative_path(self, from_path: str, to_path: str) -> str:
        return os.path.relpath(to_path, from_path)

    def get_next_page_url(self, soup: BeautifulSoup) -> str:
        next_link = soup.find('a', string="次へ")
        if next_link:
            next_url = next_link.get('href')
            if next_url:
                return next_url
        return None

    def get_next_blog_list_page_url(self, soup: BeautifulSoup) -> str:
        self.current_blog_list_page += 1
        next_link = soup.find('a', string=f"{self.current_blog_list_page}")
        if next_link:
            next_url = next_link.get('href')
            if next_url:
                return next_url
        return None

    def has_query(self, url: str, query: str) -> bool:
        return query in url

    def update_tag_url(self, tag, target_html, local_path):
        p = None
        if URLProcessor.is_diary_page(URLProcessor.remove_all_query(local_path)) or URLProcessor.is_profile_page(URLProcessor.remove_all_query(local_path)) or URLProcessor.is_blog_list_page(URLProcessor.remove_all_query(local_path)):
            p = self.create_relative_path(os.path.dirname(target_html), URLProcessor.remove_query(
                local_path)).replace("index.html", "local_index.html")
            tag['href'] = p
        elif tag.name == 'a' or tag.name == 'link':
            p = self.create_relative_path(os.path.dirname(
                target_html), URLProcessor.remove_query(local_path))
            tag['href'] = p
        elif tag.name == 'span':
            style = tag['style']
            extracted_url = URLProcessor.extract_url_from_style(style)
            p = style.replace(extracted_url, self.create_relative_path(
                os.path.dirname(target_html), URLProcessor.remove_query(local_path)))
            tag['style'] = p
        elif tag.name == 'object':
            p = self.create_relative_path(os.path.dirname(
                target_html), URLProcessor.remove_query(local_path))
            tag['data'] = p
        else:
            p = self.create_relative_path(os.path.dirname(
                target_html), URLProcessor.remove_query(local_path))
            tag['src'] = p
        if p:
            self.logger.info(f"Updated URL to '{p}' in {tag.name} tag.")
        else:
            self.logger.warning(f"Failed to update URL in {tag.name} tag.")

    def save_diary_page(self, url: str) -> str:
        base_url = re.search(r"https?://[^/]+", url).group(0)
        self.logger.info(f"Target URL: {url}")
        response = self.fetch_response(url)
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
        if self.mode == MODE.BLOG_LIST:
            return os.path.join(self.get_local_directory(URLProcessor.remove_all_query(url)), str(self.current_blog_list_page), "index.html")
        else:
            return os.path.join(self.get_local_directory(URLProcessor.remove_all_query(url)), "index.html")

    def save_response_content(self, response: requests.Response, target_html: str):
        with open(target_html, "w") as f:
            f.write(response.text)
        self.logger.info(f"Saved to '{target_html}'.")

    def get_next_url(self, soup: BeautifulSoup, base_url: str) -> str:
        next_url = self.get_next_blog_list_page_url(
            soup) if self.mode == MODE.BLOG_LIST else self.get_next_page_url(soup)
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
            if download_url is None or URLProcessor.is_external_link(base_url, download_url):
                self.logger.warning(f"External link: {download_url}")
                continue

            if not download_url.startswith("http"):
                download_url = base_url + download_url
            self.logger.info(f"Downloading from {download_url}")

            local_path = self.get_local_file_path(tag, download_url)
            FileManager.save_file(download_url, local_path, self.logger)
            self.update_tag_url(tag, target_html, local_path)

    def get_download_url(self, tag) -> str:
        if tag.name == 'span' and 'style' in tag.attrs:
            style = tag['style']
            return URLProcessor.extract_url_from_style(style)
        elif tag.name == 'a' or tag.name == 'link':
            return tag.get('href')
        elif tag.name in ['img', 'script', 'video', 'audio', 'source', 'embed']:
            return tag.get('src')
        elif tag.name == 'object':
            return tag.get('data')
        else:
            self.logger.warning(f"Skip: {tag.name}")
            return None

    def get_local_file_path(self, tag, download_url: str) -> str:
        if tag.name == 'a' and URLProcessor.is_blog_list_page(tag.get('href')):
            if self.has_query(tag.get('href'), "page="):
                page_num = tag.get_text()
                return os.path.join(self.get_local_directory(URLProcessor.remove_all_query(download_url)), page_num, "index.html")
            else:
                return os.path.join(self.get_local_directory(URLProcessor.remove_all_query(download_url)), "index.html")
        elif URLProcessor.is_api_endpoint(URLProcessor.remove_all_query(download_url)) or URLProcessor.is_home_page(URLProcessor.remove_all_query(download_url)):
            return os.path.join(self.get_local_directory(URLProcessor.remove_all_query(download_url)), "index.html")
        else:
            return os.path.join(self.get_local_directory(URLProcessor.remove_query(download_url)), os.path.basename(URLProcessor.remove_all_query(download_url)))

    def save_local_html(self, soup: BeautifulSoup, local_html: str):
        with open(local_html, "w") as f:
            f.write(soup.prettify())
        self.logger.info(f"Saved local HTML to '{local_html}'.")

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
        self.logger.info(f"Saving to '{self.save_dir}' directory.")
        if not os.path.exists(self.save_dir):
            os.mkdir(self.save_dir)
        start_time = time.time()

        url = "https://sakurazaka46.com/s/s46/diary/detail/36095?ima=0000&cd=blog"
        self.loop(url)

        url = "https://sakurazaka46.com/s/s46/artist/03?ima=0000"
        self.loop(url)

        url = "https://sakurazaka46.com/s/s46/diary/blog/list?ima=0000&page=5&ct=03&cd=blog"
        self.mode = MODE.BLOG_LIST
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
