// SPDX-License-Identifier: GPL-2.0-only WITH Classpath-exception-2.0
#include <jni.h>

extern int jni_dependency(void);
static volatile int initialized;
__attribute__((constructor)) static void initialize(void) { initialized++; }

static jint registered(JNIEnv *env, jclass type, jint value) {
    return initialized == 1 ? value + jni_dependency() : -1;
}

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM *vm, void *reserved) {
    JNIEnv *env;
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
