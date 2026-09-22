# James — FUKUSUKE Unique Code → Vendor Print API client (C#)

A typed .NET 8 client library, console demo, and unit tests for the FUKUSUKE
**"Unique Code – Vendor Print"** loyalty API (Wings Corp), built from the
API documentation.

## What the integration does

The end-to-end flow (from the API docs) is:

| Step | Owner | Action |
| ---- | ----- | ------ |
| 1 | IT Product | Generate all unique codes (status: *inactive*) |
| 2 | IT Product | **Push codes to be printed → `request-unique-code`** |
| 3 | Printing Vendor | Middleware receives codes, connects to the printing machine |
| 4 | Printing Vendor | Print packaging with the unique code |
| 5 | Printing Vendor | **Push printing completion → `confirm-unique-code`** |
| 6 | IT Product | Trigger unique code activation (≈ 2 weeks from date) |

This repository implements a client for the two bolded API calls (steps 2 and 5).

## API summary

- **Base URL:** `https://devloyaltyapi.wingscorp.com` (dev). Differs in production —
  always supply via configuration, never hard-code.
- **Auth:** `x-api-key` header.
- **Content type:** `application/json`.

### 1. Request Unique Code — `POST /v1/unique-code-prize/request-unique-code`
Reserve/generate codes for one or more materials (SKUs). **Max 500,000 codes per call.**

### 2. Confirm Unique Code — `POST /v1/unique-code-prize/confirm-unique-code`
Confirm which codes were actually printed. **Max 200,000 codes per call.**
Can return full success, `partial_success` (with `failedCodes`), or a 400
`No valid unique codes found`.

## Project layout

```
James.sln
build.bat                        # auto compile (Windows): SDK check -> build -> test -> publish EXE
run.bat                          # jalankan program (request / confirm)
config.bat                       # BaseUrl + x-api-key
src/
  Fukusuke.UniqueCode.Client/    # the reusable typed client library
    Models/                      # request/response DTOs
    Json/                        # DateOnly (yyyy-MM-dd) JSON converter
    UniqueCodeClient.cs          # HttpClient-based implementation + batching
    IUniqueCodeClient.cs
    UniqueCodeClientOptions.cs   # BaseUrl / ApiKey / Timeout + limits
    UniqueCodeApiException.cs
    ServiceCollectionExtensions.cs  # AddUniqueCodeClient(...) DI helpers
  Fukusuke.UniqueCode.Console/   # runnable demo (request / confirm verbs)
tests/
  Fukusuke.UniqueCode.Tests/     # xUnit tests (stubbed HttpClient, no network)
```

## Quick start (Windows) — auto compile

Cukup **double-click `build.bat`**. Script akan otomatis:

1. Mendeteksi .NET 8 SDK — kalau belum ada, menawarkan install otomatis
   (via `winget`, atau installer resmi Microsoft sebagai cadangan).
2. `dotnet restore` + `dotnet build -c Release`
3. Menjalankan seluruh unit test
4. Publish jadi satu file EXE di `publish\Fukusuke.UniqueCode.Console.exe`

Lalu isi API key di **`config.bat`**:

```bat
set "UniqueCodeApi__BaseUrl=https://devloyaltyapi.wingscorp.com"
set "UniqueCodeApi__ApiKey=<x-api-key Anda>"
```

Dan jalankan lewat **`run.bat`**:

```bat
run.bat request 13 6 000001 2
run.bat confirm 1 3 1 ABC123 2025-10-29
```

`run.bat` otomatis memuat `config.bat`, dan akan menanyakan API key kalau masih kosong.

> File batch yang tersedia: `build.bat` (auto compile), `run.bat` (jalankan program),
> `config.bat` (kredensial API).

## Build, test, run (manual / Linux / macOS)

Requires the **.NET 8 SDK**.

```bash
dotnet restore
dotnet build
dotnet test
```

Run the demo (configure your key first — see below):

```bash
# Request 2 codes for event 13, vendor 6, material 000001
dotnet run --project src/Fukusuke.UniqueCode.Console -- request 13 6 000001 2

# Confirm a printed code
dotnet run --project src/Fukusuke.UniqueCode.Console -- confirm 1 3 1 ABC123 2025-10-29
```

## Configuration

Bind from `appsettings.json` **or** environment variables (env vars win, and keep
secrets out of source control):

```bash
export UniqueCodeApi__BaseUrl="https://devloyaltyapi.wingscorp.com"
export UniqueCodeApi__ApiKey="<your x-api-key>"
```

`appsettings.json` ships with an empty `ApiKey` on purpose. Provide the real key
via environment variable or a user-secrets/secret-manager store.

## Using the library

```csharp
services.AddUniqueCodeClient(configuration); // binds the "UniqueCodeApi" section

// ...
public class Sender(IUniqueCodeClient client)
{
    public async Task RequestAsync()
    {
        var response = await client.RequestUniqueCodesAsync(new RequestUniqueCodeRequest
        {
            EventId = 13,
            VendorId = 6,
            Materials =
            {
                new MaterialRequest { MaterialId = "000001", PrizeId = null, Quantity = 2 },
            },
        });

        Console.WriteLine(response.Data!.BatchId);
        foreach (var code in response.Data.Materials[0].Codes)
            Console.WriteLine(code);
    }
}
```

### Automatic batching

If you have more codes than a single call allows, use the batched helpers.
They split the workload to respect the 500k / 200k per-hit limits and return
one response per underlying call:

```csharp
await client.RequestUniqueCodesBatchedAsync(bigRequest);   // splits at 500,000
await client.ConfirmUniqueCodesBatchedAsync(bigConfirm);    // splits at 200,000
```

### Error handling

Non-2xx responses throw `UniqueCodeApiException` carrying `StatusCode`,
`ApiMessage`, and the raw body. For the confirm endpoint's 400
"No valid unique codes found", the structured `data` payload is exposed via
`UniqueCodeApiException.ConfirmData`.

## Notes on the spec

- The `request-unique-code` section of the PDF lists both query params
  (`eventId`, `vendorId`, `materialId`, `quantity`) **and** a JSON request body.
  This client follows the JSON body contract shown in the worked examples, which
  carries the full `materials` array. If the deployed API expects query-string
  params instead, adjust `UniqueCodeClient.RequestUniqueCodePath`/the send logic.
- `prizeId` is modeled as a nullable string (the docs only show `null`).
- Event 13 SKU sampling (`000001`–`000015`, "Baby Happy" variants) from the docs
  is included as reference defaults in the console demo.
