// this page should be used only as a splash page to decide where a user should be navigated to
// when logged in --> to /heists
// when not logged in --> to /login

import { cookies } from "next/headers"
import { redirect } from "next/navigation"

export default async function Home() {
  // Placeholder auth check: a `session` cookie marks a logged-in user.
  // Swap this for the real session lookup once auth is implemented.
  const cookieStore = await cookies()
  const isLoggedIn = cookieStore.has("session")

  redirect(isLoggedIn ? "/heists" : "/login")
}
