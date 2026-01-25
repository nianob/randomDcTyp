let user;

async function init() {
  console.log("Activity booting");

  if (isDiscordActivity()) {
    // TODO: Implement getting user data from activity
  } else {
    const user_state = await (await fetch("/api/me", {credentials: "include"})).json();
    if (!user_state.logged_in) {
      (async () => {
        const state = crypto.randomUUID();
        sessionStorage.setItem("oauth_state", state);
        const res = await fetch("/api/config");
        const data = await res.json();
        window.location.href=data.oauth+`&state=${state}`;
      })();
      return
    }
    if (!user_state.ok) {
      console.error("User state NOT OK");
      return
    }
    user = user_state.user;
  }
  await redirect("/game.html")
}

async function redirect(url) {
  // "Redirect" safely using History API
    window.history.pushState({}, "", url);

    // Load game page content
    const html = await fetch(url).then(r => r.text());
    document.body.innerHTML = html;
}

function isDiscordActivity() {
  const params = new URLSearchParams(window.location.search);
  return (
    params.has("instance_id") &&
    params.has("frame_id")
  );
}

init();
