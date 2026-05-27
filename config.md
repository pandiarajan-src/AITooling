# OpenSpec Stack Detection Configuration

Add, remove, or rename stacks in the JSON block below.
Each key is the stack label and its value is a list of glob patterns.
If **any** pattern matches a file inside the target repository the stack
is considered detected.

Edit this file instead of modifying `setup_openspec.py`.

```json
{
  "C# / .NET":      ["*.csproj", "*.sln", "*.cs"],
  "Swift / iOS":    ["*.xcodeproj", "*.xcworkspace", "*.swift"],
  "Angular / Node": ["angular.json", "package.json", "*.ts"],
  "PowerShell":     ["*.ps1", "*.psm1"],
  "VC++":           ["*.vcxproj", "*.cpp", "*.h"]
}
```
