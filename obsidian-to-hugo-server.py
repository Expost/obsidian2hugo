import os
import shutil
import time
import re
import traceback
import json
import hashlib
import mistletoe
from mistletoe.markdown_renderer import MarkdownRenderer


class ObsidianToHugo():
    def __init__(self):
        self.md_md5 = {}
        self.cfg_name = "obsidian2hugo_cfg.json"
        self.hugo_root_path = ""
        self.obsidian_path = ""
        self.update_interval = 60

        self.parse_args()
        
        self.hugo_content_path = os.path.join(self.hugo_root_path, "content/post")

    def filter(self, ob_md): 
        '''
        判断该笔记是否需要生成笔记，这里没有使用正则，避免 #blog 标签存在于代码块或正文中时被误检测到
        '''

        with MarkdownRenderer() as r:
            with open(ob_md, "r") as f:
                doc = mistletoe.Document(f)

            # 确认标签里是否有blog字段
            for index, item in enumerate(doc.children):
                if isinstance(item, mistletoe.block_token.Paragraph):
                    # print(index, item)
                    for parga_child in item.children:
                        if isinstance(parga_child, mistletoe.span_token.RawText):
                            content = parga_child.content
                            # 获取标签
                            if content.startswith("#"): #这里肯定不是标题
                                tmp_tags= [tag[1:] for tag in content.split(" ") if tag]

                                if "blog" in tmp_tags: # 该文章需要生成为博客
                                    tmp_tags.remove("blog")
                                    return True
        return False


    def is_article_changed(self, ob_md_name):
        with open(ob_md_name, "rb") as f:
            md5 = hashlib.md5()
            md5.update(f.read())

            md5_value =  md5.hexdigest()
            if self.md_md5.get(ob_md_name) == md5_value:
                return False, ""
            
            return True, md5_value


    def replace_and_render(self,ob_files, ob_md, hugo_article_path):
        with MarkdownRenderer() as r:
            tags = {}
            with open(ob_md, "r") as f:
                doc = mistletoe.Document(f)
                for index, item in enumerate(doc.children):
                    if isinstance(item, mistletoe.block_token.Paragraph):
                        # print(index, item)
                        for parga_child in item.children:
                            if isinstance(parga_child, mistletoe.span_token.RawText):
                                content = parga_child.content

                                if content.startswith("#"): #这里肯定不是标题
                                    tmp_tags= [tag[1:] for tag in content.split(" ") if tag]

                                    if "blog" in tmp_tags: # 该文章不需要生成为博客
                                        tmp_tags.remove('blog')

                                    tags[index] = tmp_tags

                                if content.startswith("![["): #图片
                                    file_name = content[3:-2].split("|")[0].strip()
                                    print(file_name)
                                    if file_name in ob_files:
                                        dst_path = os.path.join(hugo_article_path, file_name)
                                        print(dst_path)
                                        shutil.copyfile(ob_files[file_name], dst_path)
                                        # hugo当前目录，图片按50%比例展示
                                        new_content = '<center><img src="./%s" width="50%%" /></center>' %file_name
                                        parga_child.content = new_content

                                elif content.startswith("[["): # 本地连接，暂时不做处理
                                    #file_name = content[3:-2].split("|")[0].strip()
                                    #print(file_name)
                                    pass

            # 把标签从md文档中删除
            tag_list = []
            for key in tags:
                doc.children.pop(key)
                tag_list.extend(tags[key])

            return tag_list, r.render(doc)


    def convert(self, ob_md_path, ob_files):
        md_name = os.path.basename(ob_md_path)
        title = os.path.splitext(md_name)[0]
        blog_article_dir = os.path.join(self.hugo_content_path, title)

        is_gen_blog= self.filter(ob_md_path)

        if not is_gen_blog:
            return False

        is_changed, md5_value = self.is_article_changed(ob_md_path)
        if not is_changed:
            return False

        try:
            os.mkdir(blog_article_dir)
        except:
            pass

        tags, blog_content  = self.replace_and_render(ob_files, ob_md_path, blog_article_dir)

        target_path = os.path.join(blog_article_dir, "index.md")
        time_local = time.localtime(time.time())
        dt = time.strftime("%Y-%m-%d %H:%M:%S",time_local)

        # 判断下之前是否有生成，如果有生成，那么把之前的时间正则匹配出来，用之前的时间，不要重新生成时间
        if ob_md_path in self.md_md5:
            r = re.compile("date: (.+?)\+08:00\ncategories")
            with open(target_path, "r") as f:
                con = f.read()
                dt = r.findall(con)[0]

        head = ['---',
                'title: "%s"',
                'date: %s+08:00',
                'categories: %s',
                '---',
                '',
                '%s']

        real_mark_txt =  "\n".join(head) %(title, dt, tags, blog_content)
        
        with open(target_path, "w") as f:
            f.write(real_mark_txt)

        self.md_md5[ob_md_path] = md5_value

        print("convert succ, %s --->  %s, md5: %s" %(ob_md_path, target_path, md5_value))
        return True


    def get_all_files(self, path):
        file_dict = {}
        for root, dirs, files in os.walk(path):
            for file in files:
                file_dict[file] = os.path.join(root, file)

        return file_dict

    def read_config(self):
        with open(self.cfg_name, "r") as f:
            self.md_md5 = json.loads(f.read())
            

    def write_config(self):
        with open(self.cfg_name, "w") as f:
            f.write(json.dumps(self.md_md5))
            f.flush()
            

    def commit(self):
        cur_dir = os.getcwd()
        os.chdir(self.hugo_root_path)

        os.system("git pull")
        os.system("git add .")
        os.system('git commit -m "update"')
        os.system("git push")

        os.chdir(cur_dir)
    
    def parse_args(self):
        import argparse
        parser = argparse.ArgumentParser()

        parser.add_argument("-op", dest = "obsidian_path", type=str, required = True)
        parser.add_argument("-hp", dest = "hugo_root_path", type=str, required= True)
        parser.add_argument("-i", dest = "interval", type=int, required=True)
        parser.add_argument("-b", dest="bark_url", type=str, required=False, default="")

        args = parser.parse_args()

        self.obsidian_path = args.obsidian_path
        self.hugo_root_path = args.hugo_root_path
        self.update_interval = args.interval
        self.bark_url = args.bark_url

    def notify(self, msg):
        if not self.bark_url:
            return 
        
        from urllib.parse import quote
        import requests
        print(f"notify msg: {msg}")
        msg=msg.replace("/", "\\")
        quote_msg = quote(msg)
        url =  f"{self.bark_url}/{quote_msg}"
        resp = requests.get(url, timeout = 10)
        return resp.status_code == 200

    def run(self):
        if not os.path.isfile(self.cfg_name):
            with  open(self.cfg_name, "w") as f:
                f.write("{}")

        while 1:
            try:
                self.read_config()
                ob_files = self.get_all_files(self.obsidian_path)

                new_blog = False
                for key in ob_files:
                    if key.endswith(".md"):
                        ob_md_path = ob_files[key]
                        new_blog = self.convert(ob_md_path, ob_files) or new_blog

                if new_blog:
                    self.commit()       
                    self.write_config()

                time.sleep(1 * self.update_interval)
            except Exception as e:
                excp_info = traceback.format_exc()
                self.notify("Exception\n" + excp_info)


ob = ObsidianToHugo()
ob.run()
    
    