import os
from pathlib import Path
from dotenv import load_dotenv

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

DB_PATH = Path(os.getenv("DS_AGENT_DB_PATH", str(BASE_DIR / "ds_agent.db"))).resolve()
ENABLE_CLOUD_SYNC = os.getenv("ENABLE_CLOUD_SYNC", "false").lower() == "true"
CORS_ORIGINS = [s.strip() for s in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if s.strip()]
AUTH_ALLOW_REGISTRATION = os.getenv("AUTH_ALLOW_REGISTRATION", "true").lower() == "true"
JWT_EXPIRE_MINUTES = min(1440, max(5, int(os.getenv("JWT_EXPIRE_MINUTES", "60"))))
PYTHON_TIMEOUT_SECONDS = min(60, max(1, int(os.getenv("PYTHON_TIMEOUT_SECONDS", "15"))))
PYTHON_MEMORY_MB = min(2048, max(128, int(os.getenv("PYTHON_MEMORY_MB", "512"))))
MAX_UPLOAD_BYTES = max(1024, int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))))
MAX_DATASET_ROWS = max(20, int(os.getenv("MAX_DATASET_ROWS", "100000")))
MAX_DATASET_COLUMNS = max(2, int(os.getenv("MAX_DATASET_COLUMNS", "128")))
MAX_DATASET_CELLS = max(40, int(os.getenv("MAX_DATASET_CELLS", "2000000")))
MAX_DATASET_MEMORY_BYTES = max(1024, int(os.getenv("MAX_DATASET_MEMORY_BYTES", str(100 * 1024 * 1024))))
MAX_CACHED_SESSIONS = max(1, int(os.getenv("MAX_CACHED_SESSIONS", "8")))
MAX_PROJECTS_PER_USER = max(1, int(os.getenv("MAX_PROJECTS_PER_USER", "20")))
MAX_SESSION_STORAGE_BYTES = max(1024, int(os.getenv("MAX_SESSION_STORAGE_BYTES", str(100 * 1024 * 1024))))
JOB_WORKERS = max(1, min(8, int(os.getenv("JOB_WORKERS", "3"))))
MAX_PENDING_JOBS = max(JOB_WORKERS, int(os.getenv("MAX_PENDING_JOBS", "12")))
MAX_JOBS_PER_USER = max(1, int(os.getenv("MAX_JOBS_PER_USER", "3")))
JOB_RETENTION_SECONDS = max(60, int(os.getenv("JOB_RETENTION_SECONDS", "604800")))
MAX_JOB_HISTORY = max(1, int(os.getenv("MAX_JOB_HISTORY", "200")))

# Local directories for artifacts & cache
UPLOAD_DIR = BASE_DIR / "uploads"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
REPORTS_DIR = BASE_DIR / "reports"
CHARTS_DIR = BASE_DIR / "charts"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# ───────────────────────────────────────────────────────────
# ☁️ Cloudflare R2 Storage Settings
# ───────────────────────────────────────────────────────────
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "305e8465299623c441955cbc53d3d881")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_ENDPOINT_URL = os.getenv(
    "R2_ENDPOINT_URL",
    f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
)
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "ds-agent-storage")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "https://pub-a4865e3909c8442daceb72d5bbaf5a95.r2.dev")

# ───────────────────────────────────────────────────────────
# 🗄️ Supabase Settings
# ───────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ───────────────────────────────────────────────────────────
# ⚡ GROQ API Keys (11 Accounts Round-Robin Pool)
# ───────────────────────────────────────────────────────────
GROQ_API_KEYS = [
    key.strip()
    for key in [os.getenv(f"GROQ_API_KEY_{i}") for i in range(1, 12)]
    if key and key.strip()
]
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_REASONING_MODEL = os.getenv("GROQ_REASONING_MODEL", "openai/gpt-oss-120b")
GROQ_FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
GROQ_BACKUP_MODEL = os.getenv("GROQ_BACKUP_MODEL", "qwen/qwen3.8-27b")

# ───────────────────────────────────────────────────────────
# 🤖 NVIDIA NIM API Keys (7 Accounts Round-Robin Pool)
# ───────────────────────────────────────────────────────────
NVIDIA_API_KEYS = [
    key.strip()
    for key in [os.getenv(f"NVIDIA_API_KEY_{i}") for i in range(1, 8)]
    if key and key.strip()
]
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_REASONING_MODEL = os.getenv("NVIDIA_REASONING_MODEL", "nvidia/nemotron-3-super-120b-a12b")
NVIDIA_FAST_MODEL = os.getenv("NVIDIA_FAST_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
NVIDIA_DIFFUSION_MODEL = os.getenv("NVIDIA_DIFFUSION_MODEL", "google/diffusiongemma-26b-a4b-it")
NVIDIA_VISION_MODEL = os.getenv("NVIDIA_VISION_MODEL", "meta/llama-3.2-90b-vision-instruct")
NVIDIA_GLM_MODEL = os.getenv("NVIDIA_GLM_MODEL", "z-ai/glm-5.3-flash")
NVIDIA_MUSE_MODEL = os.getenv("NVIDIA_MUSE_MODEL", "meta/muse-glimmer-30b")
NVIDIA_GPT_20B_MODEL = os.getenv("NVIDIA_GPT_20B_MODEL", "openai/gpt-oss-20b")

DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "groq")

# Task routes use these server-side pools. Keep compatibility with the exact
# Gemini variable spelling supplied in the private environment file.
GEMINI_API_KEYS = [key.strip() for i in range(1,7)
                   if (key := os.getenv(f"Gemini_ApiKey_{i}") or os.getenv(f"GEMINI_API_KEY_{i}")) and key.strip()]
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_FAST_MODEL = os.getenv("GEMINI_FAST_MODEL", "gemini-3.5-flash-lite")
GEMINI_REASONING_MODEL = os.getenv("GEMINI_REASONING_MODEL", "gemini-3.8-flash")
NVIDIA_SUPER_VL_MODEL = os.getenv("NVIDIA_SUPER_VL_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")
# Conservative per-key ceilings; 40 RPM is a limit, not unlimited NVIDIA access.
NVIDIA_RPM = max(1,min(40,int(os.getenv("NVIDIA_RPM","40"))))
GROQ_RPM = max(1,min(30,int(os.getenv("GROQ_RPM","30"))))
GROQ_TPM = max(512,int(os.getenv("GROQ_TPM","8000")))
GEMINI_FAST_RPM = max(1,min(15,int(os.getenv("GEMINI_FAST_RPM","15"))))
GEMINI_REASONING_RPM = max(1,min(5,int(os.getenv("GEMINI_REASONING_RPM","5"))))

# ───────────────────────────────────────────────────────────
# 🔐 App & Security Settings
# ───────────────────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
