function showToast(message, duration = 3000) {
    // const toast = document.getElementById("toast");
            const toast = document.createElement("div");

    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => {
      toast.classList.remove("show");
    }, duration);
  }

  function refreshUserProgress(username) {
    fetch(`/refresh_user/${username}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          showToast(`${username} 님\n✅ 풀이 데이터 갱신 완료!`);
          print("갱신 완료")
          setTimeout(() => {
            location.reload();
          }, 1500);
        } else {
          showToast("❌ 풀이 데이터 갱신에 실패했습니다.");
          console.error("Error:", data.error);
          print("갱신 실패")
        }
      })
      .catch((err) => {
        showToast("⚠️ 네트워크 오류: 서버에 연결할 수 없습니다.");
        console.error("Fetch error:", err);
      });
  }