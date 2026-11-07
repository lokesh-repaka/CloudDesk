import { NextResponse } from "next/navigation";

export async function GET() {
  return Response.json(
    {
      status: "ok",
      timestamp: new Date().toISOString(),
      service: "clouddesk-frontend",
      version: "0.1.0",
    },
    {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store, max-age=0",
      },
    }
  );
}

