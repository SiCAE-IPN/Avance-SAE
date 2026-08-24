import os
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "frontend", "Templates"))
static = StaticFiles(directory=os.path.join(BASE_DIR, "frontend", "static"))

def formato_miles(val):
    if val is None or val == '':
        return '0'
    try:
        n = int(float(str(val).replace(',', '').strip()))
        return f"{n:,}"
    except Exception:
        return str(val)

templates.env.filters['formato_miles'] = formato_miles
templates.env.filters['miles'] = formato_miles

if __name__ == "__main__":
    print(BASE_DIR)