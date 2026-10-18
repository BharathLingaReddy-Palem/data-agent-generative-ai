"""Windows Job Object: assign a suspended worker before allowing it to run."""
import ctypes
from ctypes import wintypes


def constrain_windows(process, memory_mb, cpu_seconds):
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    class Basic(ctypes.Structure):
        _fields_ = [('ProcessTime',ctypes.c_int64),('JobTime',ctypes.c_int64),('Flags',wintypes.DWORD),
                    ('MinWorking',ctypes.c_size_t),('MaxWorking',ctypes.c_size_t),
                    ('ActiveProcess',wintypes.DWORD),('Affinity',ctypes.c_size_t),
                    ('Priority',wintypes.DWORD),('Scheduling',wintypes.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name,ctypes.c_uint64) for name in ('ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes')]
    class Extended(ctypes.Structure):
        _fields_ = [('Basic',Basic),('IO',IO),('ProcessMemory',ctypes.c_size_t),
                    ('JobMemory',ctypes.c_size_t),('PeakProcess',ctypes.c_size_t),('PeakJob',ctypes.c_size_t)]
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p,wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE,wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None,None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = Extended()
    limits.Basic.Flags = 0x100 | 0x200 | 0x2 | 0x4 | 0x8 | 0x2000
    limits.Basic.ProcessTime = int(cpu_seconds*10_000_000)
    limits.Basic.JobTime = int(cpu_seconds*10_000_000)
    # Windows virtualenv's launcher creates the actual interpreter as a child.
    limits.Basic.ActiveProcess = 2
    limits.ProcessMemory = memory_mb*1024*1024
    limits.JobMemory = memory_mb*1024*1024
    try:
        if not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(job,wintypes.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())
        ntdll = ctypes.WinDLL('ntdll')
        ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        ntdll.NtResumeProcess.restype = ctypes.c_long
        if ntdll.NtResumeProcess(wintypes.HANDLE(int(process._handle))) != 0:
            raise RuntimeError('Unable to resume constrained worker.')
    except BaseException:
        kernel.CloseHandle(job)
        raise
    return lambda: kernel.CloseHandle(job)
