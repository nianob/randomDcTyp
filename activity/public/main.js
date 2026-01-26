let DiscordSDK;
let discordSdk;

async function init() {
  console.log("Activity booting");
  const user_state = await (await fetch("/api/me", { credentials: "include" })).json();
  const res = await fetch("/api/config");
  const data = await res.json();
  if (isDiscordActivity()) {
    if (!user_state.logged_in) {
      const sdk = await import("@discord/embedded-app-sdk");
      DiscordSDK = sdk.DiscordSDK;
      discordSdk = new DiscordSDK(data.bot_id);
      await discordSdk.ready()
      const { code } = await discordSdk.commands.authorize({
        client_id: data.bot_id,
        response_type: "code",
        state: "",
        prompt: "none",
        scope: [
          "identify"
        ]
      }) 
      const authres = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code })
      })
      const auth = await authres.json();
      if (!auth.ok) {
        throw Error("Unable to Authenticate")
      }
    }
  } else {
    if (!user_state.logged_in) {
      (async () => {
        const state = crypto.randomUUID();
        sessionStorage.setItem("oauth_state", state);
        window.location.href = data.oauth + `&state=${state}`;
      })();
      return
    }
      if (!user_state.ok) {
        document.getElementById("title").innerText = "Authentication Failed";
        document.getElementById("reauth").onclick = () => {
          const state = crypto.randomUUID();
          sessionStorage.setItem("oauth_state", state);
          window.location.href = data.oauth + `&state=${state}`;
        }
        document.getElementById("reauth").hidden = false;
        return
      }
  }
  await redirect("/game.html");
}

async function redirect(url) {
  // "Redirect" safely using History API
  window.history.pushState({}, "", url);

  // Load game page content
  const html = await fetch(url).then(r => r.text());
  document.body.innerHTML = html;
  try {
    const script = document.createElement("script");
    script.src = url.replace(/\.html$/, ".js");
    script.type = "module";
    script.dataset.page = "true";
    document.body.appendChild(script);
  } catch (e) {
    console.log(`No json for ${url}`);
  }
}

function isDiscordActivity() {
  const params = new URLSearchParams(window.location.search);
  return (
    params.has("instance_id") &&
    params.has("frame_id")
  );
}

init();
