import csv
import os
import random
from abc import ABC, abstractmethod

import pandas as pd
import pkg_resources
import requests


class BaseDownloader(ABC):
    """Abstract base class for downloading street view images.

    This class provides common functionality for downloading street view images from
    different providers. It handles user agents, proxies, logging and checking for
    already downloaded images.

    Attributes:
        _log_path (str): Path to log file for recording downloaded image IDs
        _user_agents (list): List of user agent strings to use for requests
        _proxies (list): List of proxy servers to use for requests
    """

    @abstractmethod
    def __init__(self, log_path=None):
        """Initialize the downloader.

        Args:
            log_path (str, optional): Path to log file. Defaults to None.
        """
        self._log_path = log_path
        self._user_agents = self._get_ua()
        self._proxies = self._get_proxies()

    @property
    def log_path(self):
        """Property for log_path.

        Returns:
            str: Path to the log file
        """
        return self._log_path

    @log_path.setter
    def log_path(self, log_path):
        """Setter for log_path.

        Args:
            log_path (str): Path to the log file
        """
        self._log_path = log_path

    def _get_proxies(self):
        """Get list of proxy servers from CSV file.

        Returns:
            list: List of dictionaries containing proxy information
        """
        proxies_file = pkg_resources.resource_filename("zensvi.download.utils", "proxies.csv")
        proxies = []
        # open with "utf-8" encoding to avoid UnicodeDecodeError
        with open(proxies_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ip = row["ip"]
                port = row["port"]
                protocols = row["protocols"]
                proxy_dict = {protocols: f"{ip}:{port}"}
                proxies.append(proxy_dict)
        return proxies

    def _get_ua(self):
        """Get list of user agents from CSV file.

        Returns:
            list: List of dictionaries containing user agent strings
        """
        user_agent_file = pkg_resources.resource_filename("zensvi.download.utils", "UserAgent.csv")
        UA = []
        with open(user_agent_file, "r") as f:
            for line in f:
                ua = {"user_agent": line.strip()}
                UA.append(ua)
        return UA

    def _request_get(
        self,
        url,
        *,
        headers=None,
        timeout=10,
        allow_redirects=True,
        max_attempts=5,
        use_proxies=True,
        check_status=False,
    ):
        """Perform a GET request with retries and optional proxy fallback.

        This helper ensures that a direct connection is attempted before
        falling back to configured proxies. It retries the request up to
        ``max_attempts`` times and raises the last encountered exception if all
        attempts fail.

        Args:
            url (str): The URL to request.
            headers (dict, optional): Optional request headers. Defaults to
                None.
            timeout (int, optional): Timeout in seconds for the request.
                Defaults to 10.
            allow_redirects (bool, optional): Whether to allow redirects.
                Defaults to True.
            max_attempts (int, optional): Maximum number of attempts before
                giving up. Defaults to 5.
            use_proxies (bool, optional): Whether to use configured proxies
                after the direct attempt. Defaults to True.
            check_status (bool, optional): If True, call ``raise_for_status``
                on the response before returning it. Defaults to False.

        Returns:
            requests.Response: The HTTP response object.

        Raises:
            requests.exceptions.RequestException: If all attempts fail.
        """

        attempts = 0
        last_exception = None
        proxy_pool = self._proxies if use_proxies and self._proxies else []

        while attempts < max_attempts:
            if attempts == 0 or not proxy_pool:
                proxy = None
            else:
                proxy = random.choice(proxy_pool)

            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=allow_redirects,
                    proxies=proxy,
                )
                if check_status:
                    response.raise_for_status()
                return response
            except requests.exceptions.RequestException as exc:
                last_exception = exc
                attempts += 1
                continue

        if last_exception is not None:
            raise last_exception
        raise requests.exceptions.RequestException("Failed to fetch URL")

    def _log_write(self, pids):
        """Write panorama IDs to log file.

        Args:
            pids (list): List of panorama IDs to log
        """
        if self.log_path is None:
            return
        with open(self.log_path, "a+") as fw:
            for pid in pids:
                fw.write(pid + "\n")

    def _check_already(self, all_panoids):
        """Check which panorama IDs have already been downloaded.

        Args:
            all_panoids (list): List of all panorama IDs to check

        Returns:
            list: List of panorama IDs that have not been downloaded yet
        """
        # Get the set of already downloaded images
        name_r = set()
        for dirpath, dirnames, filenames in os.walk(self.panorama_output):
            for name in filenames:
                name_r.add(name.split(".")[0])

        # Filter the list of all panoids to only include those not already downloaded
        all_panoids = list(set(all_panoids) - name_r)
        return all_panoids

    def _read_pids(self, path_pid, start_date, end_date):
        """Read and filter panorama IDs from CSV file.

        Args:
            path_pid (str): Path to CSV file containing panorama IDs
            start_date (str): Start date for filtering
            end_date (str): End date for filtering

        Returns:
            list: List of filtered panorama IDs
        """
        pid_df = pd.read_csv(path_pid)
        # filter pids by date
        pid_df = self._filter_pids_date(pid_df, start_date, end_date)
        # get unique pids as a list
        pids = pid_df.iloc[:, 0].unique().tolist()
        return pids

    @abstractmethod
    def _filter_pids_date(self, pid_df, start_date, end_date):
        """Filter panorama IDs by date range.

        Args:
            pid_df (pandas.DataFrame): DataFrame containing panorama IDs and dates
            start_date (str): Start date for filtering
            end_date (str): End date for filtering

        Returns:
            pandas.DataFrame: Filtered DataFrame
        """
        pass

    @abstractmethod
    def download_svi(
        self,
        dir_output,
        lat=None,
        lon=None,
        input_csv_file="",
        input_shp_file="",
        input_place_name="",
        id_columns=None,
        buffer=0,
        update_pids=False,
        start_date=None,
        end_date=None,
        metadata_only=False,
    ):
        """Download street view images.

        Args:
            dir_output (str): Output directory for downloaded images
            lat (float, optional): Latitude. Defaults to None.
            lon (float, optional): Longitude. Defaults to None.
            input_csv_file (str, optional): Input CSV file path. Defaults to "".
            input_shp_file (str, optional): Input shapefile path. Defaults to "".
            input_place_name (str, optional): Input place name. Defaults to "".
            id_columns (list, optional): ID columns. Defaults to None.
            buffer (float, optional): Buffer distance. Defaults to 0.
            update_pids (bool, optional): Whether to update PIDs. Defaults to False.
            start_date (str, optional): Start date for filtering. Defaults to None.
            end_date (str, optional): End date for filtering. Defaults to None.
            metadata_only (bool, optional): Whether to download metadata only. Defaults to False.
        """
        pass
