from django.shortcuts import redirect

_PUBLIC_PREFIXES = ("/login/", "/admin/")


class PasswordGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not any(request.path.startswith(p) for p in _PUBLIC_PREFIXES):
            if not request.session.get("authenticated"):
                return redirect(f"/login/?next={request.path}")
        return self.get_response(request)
