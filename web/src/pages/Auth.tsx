import { useState } from "react";
import { ArrowRight, Layers3 } from "lucide-react";
import { post } from "../api";
import { Form, values } from "../components/UI";

export default function Auth({
  initialized,
  needsToken,
  onLogin,
}: {
  initialized: boolean;
  needsToken: boolean;
  onLogin: () => void;
}) {
  const [setup, setSetup] = useState(!initialized);
  return (
    <main className="auth-page">
      <div className="auth-panel">
        <div className="brand auth-brand">
          <span className="brand-mark">
            <Layers3 size={25} />
          </span>
          <span>行序</span>
        </div>
        <h1>{setup ? "创建管理员" : "登录"}</h1>
        <Form
          label={setup ? "创建并登录" : "登录"}
          onSubmit={async (f) => {
            const body = values(f);
            if (setup) {
              await post("/auth/setup", body);
              setSetup(false);
            }
            await post("/auth/login", body);
            onLogin();
          }}
        >
          <label>
            账号
            <input
              name="username"
              minLength={2}
              maxLength={80}
              autoComplete="username"
              required
              autoFocus
            />
          </label>
          <label>
            密码
            <input
              name="password"
              type="password"
              minLength={12}
              maxLength={128}
              autoComplete={setup ? "new-password" : "current-password"}
              required
            />
          </label>
          {setup && needsToken && (
            <label>
              初始化凭证
              <input name="setup_token" type="password" required />
            </label>
          )}
        </Form>
        <ArrowRight className="auth-arrow" size={36} />
      </div>
    </main>
  );
}
