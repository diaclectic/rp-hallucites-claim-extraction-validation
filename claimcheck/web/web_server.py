import functools
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from claimcheck.web.request_handler import RequestHandler, Route


class WebServer:
    """A local web server for the review page, listening only on 127.0.0.1.

    It serves `static/` and the command's API routes.
    """

    STATIC_DIR = Path(__file__).with_name("static")

    def __init__(
        self, routes: dict[str, Route], page: str, static_dir: Path | None = None, open_browser: bool = True
    ) -> None:
        self.routes = routes
        self.page = page
        self.static_root = static_dir or self.STATIC_DIR
        self.open_browser = open_browser
        self._stopped = threading.Event()
        self._server: ThreadingHTTPServer | None = None

    @property
    def url(self) -> str:
        """The address of the page, once started."""
        return f"http://127.0.0.1:{self._server.server_address[1]}/"

    def start(self) -> None:
        """Start serving on a random free port, print the address, and open the browser."""
        handler = functools.partial(RequestHandler, routes=self.routes, static_dir=self.static_root, page=self.page)
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        print(f"claimcheck is running at {self.url}  (Ctrl-C to stop)", flush=True)
        if self.open_browser and not webbrowser.open(self.url):
            print("Open that address in your browser.")

    def stop(self) -> None:
        """Ask `wait` to return shortly, once the current response has been sent. Safe to call from a request."""
        threading.Timer(0.3, self._stopped.set).start()

    def wait(self) -> None:
        """Block until `stop` is called or the user presses Ctrl-C, then shut the server down."""
        try:
            self._stopped.wait()
        except KeyboardInterrupt:
            print()
        finally:
            self.close()

    def close(self) -> None:
        """Shut the server down."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
