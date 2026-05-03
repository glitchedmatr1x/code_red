#include <type_traits>
using BOOL=int; using Actor=int; using Layout=int;
struct Vector2 { float x; float y; };
struct Vector3 { float x; float y; float z; };
template <typename R, typename... Args>
R nativeInvoke(unsigned long long, Args...) { if constexpr (!std::is_same_v<R, void>) return R{}; }
#include "native_bridge_selected_wrappers.cpp"
int main(){ return codered_native_bridge::kSelectedNatives[0].hash ? 0 : 1; }
