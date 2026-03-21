import os

# ========================================================
# 1. 설정: 무시할 폴더 및 파일 확장자 (노이즈 제거)
# ========================================================
IGNORE_DIRS = {
    '.git', '__pycache__', 'node_modules', 'venv', '.env', 
    'dist', 'build', '.vscode', '.idea', 'assets', 'images'
}
IGNORE_EXTS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', 
    '.zip', '.tar', '.gz', '.exe', '.bin', '.pyc'
}
OUTPUT_FILE = "project_context.txt"

def pack_project():
    current_dir = os.getcwd()
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
        # 프로젝트 구조(트리) 먼저 보여주기
        outfile.write("=== PROJECT DIRECTORY STRUCTURE ===\n")
        for root, dirs, files in os.walk(current_dir):
            # 무시할 폴더 제외
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            level = root.replace(current_dir, '').count(os.sep)
            indent = ' ' * 4 * (level)
            outfile.write(f"{indent}{os.path.basename(root)}/\n")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                if not any(f.endswith(ext) for ext in IGNORE_EXTS) and f != "packer.py" and f != OUTPUT_FILE:
                    outfile.write(f"{subindent}{f}\n")
        
        outfile.write("\n\n=== FILE CONTENTS ===\n")

        # 실제 파일 내용 쓰기
        for root, dirs, files in os.walk(current_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # 무시할 확장자 및 자기 자신 제외
                if any(file.endswith(ext) for ext in IGNORE_EXTS) or file in ["packer.py", OUTPUT_FILE]:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        content = infile.read()
                        
                        # 구분선과 파일 경로 명시 (제미나이가 파일별로 인식하게 함)
                        outfile.write(f"\n\n{'='*50}\n")
                        outfile.write(f"FILE PATH: {os.path.relpath(file_path, current_dir)}\n")
                        outfile.write(f"{'='*50}\n")
                        outfile.write(content)
                        print(f"✅ Packed: {file}")
                except Exception as e:
                    print(f"⚠️ Skipped (Error): {file}")

    print(f"\n🎉 완료! '{OUTPUT_FILE}' 파일이 생성되었습니다.")
    print("이 파일을 제미나이에게 업로드하세요.")

if __name__ == "__main__":
    pack_project()