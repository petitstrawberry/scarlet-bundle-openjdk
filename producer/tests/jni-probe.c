// SPDX-License-Identifier: GPL-2.0-only WITH Classpath-exception-2.0
#include <jni.h>
#include <stdlib.h>
#include <pthread.h>

extern int jni_dependency(void);
static volatile int initialized;
static JavaVM *java_vm;
__attribute__((constructor)) static void initialize(void) { initialized++; }

static jint registered(JNIEnv *env, jclass type, jint value) {
    return initialized == 1 ? value + jni_dependency() : -1;
}

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM *vm, void *reserved) {
    JNIEnv *env;
    java_vm = vm;
    if ((*vm)->GetEnv(vm, (void **)&env, JNI_VERSION_1_8) != JNI_OK) return JNI_ERR;
    jclass type = (*env)->FindClass(env, "Jni");
    if (!type) return JNI_ERR;
    JNINativeMethod methods[] = {{"registered", "(I)I", (void *)registered}};
    if ((*env)->RegisterNatives(env, type, methods, 1) != JNI_OK) return JNI_ERR;
    return JNI_VERSION_1_8;
}

JNIEXPORT jint JNICALL Java_Jni_exercise(JNIEnv *env, jclass type, jbyteArray data, jobject buffer) {
    jmethodID callback = (*env)->GetStaticMethodID(env, type, "callback", "(I)I");
    if (!callback || (*env)->GetArrayLength(env, data) != 3) return -1;
    jbyte *copy = malloc(3);
    if (!copy) return -1;
    (*env)->GetByteArrayRegion(env, data, 0, 3, copy);
    int valid = copy[0] == 1 && copy[1] == 2 && copy[2] == 3;
    free(copy);
    if (!valid) return -1;
    jbyte value = 42;
    (*env)->SetByteArrayRegion(env, data, 1, 1, &value);
    jbyte *direct = (*env)->GetDirectBufferAddress(env, buffer);
    if (!direct || (*env)->GetDirectBufferCapacity(env, buffer) != 8) return -1;
    direct[0] = 99;
    return (*env)->CallStaticIntMethod(env, type, callback, jni_dependency());
}

JNIEXPORT void JNICALL Java_Jni_fail(JNIEnv *env, jclass type) {
    jclass exception = (*env)->FindClass(env, "java/lang/IllegalStateException");
    if (exception) (*env)->ThrowNew(env, exception, "native exception");
}

static void *attached_thread(void *result) {
    JNIEnv *env;
    if ((*java_vm)->AttachCurrentThread(java_vm, (void **)&env, NULL) != JNI_OK) return NULL;
    jclass type = (*env)->FindClass(env, "Jni");
    if (type) {
        jmethodID callback = (*env)->GetStaticMethodID(env, type, "callback", "(I)I");
        if (callback) *(jint *)result = (*env)->CallStaticIntMethod(env, type, callback, 43);
    }
    if ((*env)->ExceptionCheck(env)) {
        (*env)->ExceptionClear(env);
        *(jint *)result = -1;
    }
    if ((*java_vm)->DetachCurrentThread(java_vm) != JNI_OK) *(jint *)result = -1;
    return NULL;
}

JNIEXPORT jint JNICALL Java_Jni_attached(JNIEnv *env, jclass type) {
    pthread_t thread;
    jint result = -1;
    if (pthread_create(&thread, NULL, attached_thread, &result) != 0) return -1;
    if (pthread_join(thread, NULL) != 0) return -1;
    return result;
}
