// Experimental v6 cold-start instrumentation — isolated validation only. Never deploy directly to a live daemon.
// Preserve Apple's conversions; normalize only the documented private ordinal.
#import <Foundation/Foundation.h>
#import <EventKit/EventKit.h>
#import <objc/runtime.h>
#import <objc/message.h>
#import <sys/sysctl.h>
#import <dlfcn.h>
#import <stdatomic.h>
#import <string.h>

#if !defined(__x86_64__)
#error This experimental candidate is restricted to macOS Intel x86_64.
#endif
#ifndef EXS_EXPECTED_BUILD
#define EXS_EXPECTED_BUILD "25G241"
#endif

static id (*originalFromEXS)(id, SEL, id) = NULL;
static void (*originalToEXS)(id, SEL, id, id) = NULL;
static atomic_int installed = 0;
static atomic_int actual_installer_source = 0; // 1 ctor, 2 dlopen, 3 worker, 0 direct
#ifdef EXS_LAB_TRANSIENT_FAIL_COUNT
static atomic_int transient_remaining = EXS_LAB_TRANSIENT_FAIL_COUNT;
#endif
static atomic_int build_gate = 0; // 0 unknown; 1 exact build; -1 different/unavailable

static BOOL checkBuild(void) {
    int prior = atomic_load_explicit(&build_gate, memory_order_acquire);
    if (prior) return prior == 1;
    char buf[128] = {0};
    size_t len = sizeof(buf);
    BOOL good = sysctlbyname("kern.osversion", buf, &len, NULL, 0) == 0 &&
                len > 0 && len < sizeof(buf) &&
                strcmp(buf, EXS_EXPECTED_BUILD) == 0;
    atomic_store_explicit(&build_gate, good ? 1 : -1, memory_order_release);
    return good;
}

__attribute__((visibility("default")))
int exchange_last_weekday_build_compatible(void) { return checkBuild() ? 1 : 0; }

static id fixedFromEXS(id cls, SEL selector, id properties) {
    id result = originalFromEXS(cls, selector, properties);
    if (![result isKindOfClass:[NSArray class]]) return result;
    NSMutableArray *changed = nil;
    NSUInteger count = [result count];
    for (NSUInteger i = 0; i < count; ++i) {
        id day = [result objectAtIndex:i];
        if (![day isKindOfClass:[EKRecurrenceDayOfWeek class]] || [day weekNumber] != 5)
            continue;
        EKRecurrenceDayOfWeek *replacement =
            [EKRecurrenceDayOfWeek dayOfWeek:[day dayOfTheWeek] weekNumber:-1];
        if (replacement) {
            if (!changed) changed = [result mutableCopy];
            [changed replaceObjectAtIndex:i withObject:replacement];
        }
    }
    return changed ?: result;
}

static void fixedToEXS(id cls, SEL selector, id days, id properties) {
    originalToEXS(cls, selector, days, properties);
    if (![days isKindOfClass:[NSArray class]] || [days count] == 0 || !properties)
        return;
    for (id day in days) {
        if (![day isKindOfClass:[EKRecurrenceDayOfWeek class]] ||
            [day weekNumber] != -1) return;
    }
    SEL setter = sel_registerName("setRecurrenceDayOfWeekIndex:");
    if ([properties respondsToSelector:setter]) {
        ((void (*)(id, SEL, NSInteger))objc_msgSend)(properties, setter, 5);
    }
}

static BOOL hasEncoding(Method method, const char *encoding) {
    return method && method_getTypeEncoding(method) &&
           strcmp(method_getTypeEncoding(method), encoding) == 0;
}

static BOOL fromConsumer(IMP imp) {
    Dl_info info = {0};
    return imp && dladdr((const void *)imp, &info) != 0 && info.dli_fname &&
           strstr(info.dli_fname, "EventKitDataConsumer.dataconsumer/") != NULL;
}

//  0 newly installed; 1 already installed; -1 consumer not registered;
// -2 method missing; -3 ABI mismatch; -4 unexpected existing hook;
// -5 macOS build not explicitly approved; -6 implementation outside expected bundle;
// -7 Exchange properties ABI changed; -8 properties class not registered yet.
__attribute__((visibility("default")))
int exchange_last_weekday_install_from(int source) {
    if (!checkBuild()) return -5;
#ifdef EXS_LAB_TRANSIENT_FAIL_COUNT
    // Fault injection only in the dedicated LAB build. Never ship this target.
    int n = atomic_load_explicit(&transient_remaining, memory_order_relaxed);
    while (n > 0 && !atomic_compare_exchange_weak_explicit(
               &transient_remaining, &n, n - 1,
               memory_order_acq_rel, memory_order_relaxed)) {}
    if (n > 0) return -8;
#endif
    @synchronized ([NSObject class]) {
        if (atomic_load_explicit(&installed, memory_order_acquire)) return 1;
        Class cls = objc_getClass("EXSEKRecurrenceUtils");
        if (!cls) return -1;
        Method forward = class_getClassMethod(cls, sel_registerName("daysOfTheWeekFromPropertiesWithEK:"));
        Method reverse = class_getClassMethod(cls, sel_registerName("EKdaysOfTheWeek:toProperties:"));
        if (!forward || !reverse) return -2;
        if (!hasEncoding(forward, "@24@0:8@16") ||
            !hasEncoding(reverse, "v32@0:8@16@24")) return -3;
        Class props = objc_getClass("EXSCalendarItemProperties");
        if (!props) return -8;
        if (!hasEncoding(class_getInstanceMethod(props, sel_registerName("recurrenceDayOfWeekIndex")), "q16@0:8") ||
            !hasEncoding(class_getInstanceMethod(props, sel_registerName("setRecurrenceDayOfWeekIndex:")), "v24@0:8q16") ||
            !hasEncoding(class_getInstanceMethod(props, sel_registerName("recurrenceDaysOfWeek")), "Q16@0:8") ||
            !hasEncoding(class_getInstanceMethod(props, sel_registerName("setRecurrenceDaysOfWeek:")), "v24@0:8Q16"))
            return -7;
        IMP oldForward = method_getImplementation(forward);
        IMP oldReverse = method_getImplementation(reverse);
        if (!oldForward || !oldReverse ||
            oldForward == (IMP)fixedFromEXS || oldReverse == (IMP)fixedToEXS)
            return -4;
        if (!fromConsumer(oldForward) || !fromConsumer(oldReverse)) return -6;
        originalFromEXS = (id (*)(id, SEL, id))oldForward;
        originalToEXS = (void (*)(id, SEL, id, id))oldReverse;
        // Still a short interval between two swaps. This is NOT a claim of
        // complete atomicity, nor proof against execution during bundle +load.
        method_setImplementation(forward, (IMP)fixedFromEXS);
        method_setImplementation(reverse, (IMP)fixedToEXS);
        atomic_store_explicit(&actual_installer_source, source, memory_order_release);
        atomic_store_explicit(&installed, 1, memory_order_release);
        return 0;
    }
}

__attribute__((visibility("default")))
int exchange_last_weekday_install(void) {
    return exchange_last_weekday_install_from(0);
}

__attribute__((visibility("default")))
int exchange_last_weekday_actual_installer_source(void) {
    if (!atomic_load_explicit(&installed, memory_order_acquire)) return 0;
    return atomic_load_explicit(&actual_installer_source, memory_order_acquire);
}

__attribute__((visibility("default")))
int exchange_last_weekday_installed(void) {
    return atomic_load_explicit(&installed, memory_order_acquire);
}

__attribute__((visibility("default")))
int exchange_last_weekday_patch_version(void) { return 6; }
