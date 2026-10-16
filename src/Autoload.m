// v6 diagnostic laboratory: startup progress remains observable and *transient*
// initialization failures do not silently end the fallback worker.
// This does NOT claim to eliminate all races inside dyld or Objective-C +load.
#include <dlfcn.h>
#include <stdint.h>
#include <pthread.h>
#include <unistd.h>
#include <string.h>
#include <os/log.h>
#include <stdatomic.h>

extern int exchange_last_weekday_install_from(int source);
extern int exchange_last_weekday_actual_installer_source(void);

static atomic_int startup_state = 0; // 0 pending, 1 installed, -1 permanently rejected
static atomic_int startup_source = 0; // original installer: 1 constructor, 2 dlopen, 3 worker
static atomic_int relevant_dlopen = 0;
static atomic_int relevant_dlopen_installed = 0;
static atomic_int attempts = 0;
static atomic_int last_result = -99;
static atomic_int constructor_entered = 0;
static atomic_int initial_result = -99;
static atomic_int worker_started = 0;
static atomic_int worker_running = 0;
static atomic_int worker_finished = 0;
static __thread int in_interposer = 0;

__attribute__((visibility("default")))
int exchange_last_weekday_autoload_state(void) { return atomic_load(&startup_state); }
__attribute__((visibility("default")))
int exchange_last_weekday_startup_source(void) { return atomic_load(&startup_source); }
__attribute__((visibility("default")))
int exchange_last_weekday_seen_plugin_dlopen(void) { return atomic_load(&relevant_dlopen); }
__attribute__((visibility("default")))
int exchange_last_weekday_installed_after_dlopen(void) { return atomic_load(&relevant_dlopen_installed); }
__attribute__((visibility("default")))
int exchange_last_weekday_attempt_count(void) { return atomic_load(&attempts); }
__attribute__((visibility("default")))
int exchange_last_weekday_last_result(void) { return atomic_load(&last_result); }
__attribute__((visibility("default")))
int exchange_last_weekday_constructor_entered(void) { return atomic_load(&constructor_entered); }
__attribute__((visibility("default")))
int exchange_last_weekday_initial_result(void) { return atomic_load(&initial_result); }
__attribute__((visibility("default")))
int exchange_last_weekday_worker_started(void) { return atomic_load(&worker_started); }
__attribute__((visibility("default")))
int exchange_last_weekday_worker_running(void) { return atomic_load(&worker_running); }
__attribute__((visibility("default")))
int exchange_last_weekday_worker_finished(void) { return atomic_load(&worker_finished); }

// -1 consumer class missing, -2 methods not yet registered, -8 properties
// class missing. These can be transient. An actual ABI mismatch (-3 or -7),
// unexpected existing hook (-4), build mismatch (-5), or unexpected source (-6)
// is a permanent refusal, never retried into a patch.
static int is_transient(int rc) { return rc == -1 || rc == -2 || rc == -8; }

static int attempt(int source) {
    atomic_fetch_add_explicit(&attempts, 1, memory_order_relaxed);
    int rc = exchange_last_weekday_install_from(source);
    atomic_store_explicit(&last_result, rc, memory_order_release);
    return rc;
}

static void record(int rc, int observer_source) {
    if (rc == 0 || rc == 1) {
        int actual = exchange_last_weekday_actual_installer_source();
        atomic_store_explicit(&startup_source, actual, memory_order_release);
        if (atomic_exchange_explicit(&startup_state, 1, memory_order_acq_rel) != 1)
            os_log_info(OS_LOG_DEFAULT,
                "ExchangeLastWeekdayFix v6: both hooks installed (actual_source=%{public}d, observer=%{public}d, result=%{public}d)",
                actual, observer_source, rc);
    } else if (!is_transient(rc)) {
        if (atomic_exchange_explicit(&startup_state, -1, memory_order_acq_rel) != -1)
            os_log_error(OS_LOG_DEFAULT,
                "ExchangeLastWeekdayFix v6: REFUSED permanent incompatibility (code=%{public}d, observer=%{public}d)",
                rc, observer_source);
    }
}

static void *wait_for_consumer(void *unused) {
    (void)unused;
    atomic_store_explicit(&worker_running, 1, memory_order_release);
    os_log_info(OS_LOG_DEFAULT, "ExchangeLastWeekdayFix v6: fallback worker entered");
    for (unsigned n = 0;; ++n) {
        if (atomic_load_explicit(&startup_state, memory_order_acquire) != 0) break;
        int rc = attempt(3);
        record(rc, 3);
        if (!is_transient(rc)) break;
        if (n == 40 || (n > 40 && n % 60 == 40))
            os_log_error(OS_LOG_DEFAULT,
                "ExchangeLastWeekdayFix v6: still pending (last_rc=%{public}d, attempts=%{public}d)",
                rc, atomic_load(&attempts));
        usleep(n < 40 ? 100000 : 1000000);
    }
    os_log_info(OS_LOG_DEFAULT,
        "ExchangeLastWeekdayFix v6: fallback worker finished (state=%{public}d, attempts=%{public}d)",
        atomic_load(&startup_state), atomic_load(&attempts));
    atomic_store_explicit(&worker_running, 0, memory_order_release);
    atomic_store_explicit(&worker_finished, 1, memory_order_release);
    return NULL;
}

static void *exs_dlopen(const char *filename, int mode) {
    void *handle = dlopen(filename, mode);
    if (handle && !in_interposer && filename &&
        strstr(filename, "EventKitDataConsumer") != NULL) {
        in_interposer = 1;
        atomic_fetch_add_explicit(&relevant_dlopen, 1, memory_order_relaxed);
        int rc = attempt(2);
        if (rc == 0 || rc == 1)
            atomic_fetch_add_explicit(&relevant_dlopen_installed, 1, memory_order_relaxed);
        record(rc, 2);
        in_interposer = 0;
    }
    return handle;
}

__attribute__((used))
static struct {
    const void *replacement;
    const void *replacee;
} exs_dlopen_interpose __attribute__((section("__DATA,__interpose"))) = {
    (const void *)(uintptr_t)&exs_dlopen,
    (const void *)(uintptr_t)&dlopen
};

__attribute__((constructor))
static void autoload(void) {
    atomic_store_explicit(&constructor_entered, 1, memory_order_release);
    int rc = attempt(1);
    atomic_store_explicit(&initial_result, rc, memory_order_release);
    // Diagnostic LAB: error-level to preserve the first cold-boot decision.
    os_log_error(OS_LOG_DEFAULT,
        "ExchangeLastWeekdayFix v6: constructor entered (initial_rc=%{public}d)", rc);
    record(rc, 1);
    if (!is_transient(rc)) return;
    pthread_t thread;
    int err = pthread_create(&thread, NULL, wait_for_consumer, NULL);
    if (err != 0) {
        os_log_error(OS_LOG_DEFAULT,
            "ExchangeLastWeekdayFix v6: fallback worker creation failed (error=%{public}d)", err);
        return;
    }
    atomic_store_explicit(&worker_started, 1, memory_order_release);
    pthread_detach(thread);
    os_log_info(OS_LOG_DEFAULT, "ExchangeLastWeekdayFix v6: fallback worker created");
}
