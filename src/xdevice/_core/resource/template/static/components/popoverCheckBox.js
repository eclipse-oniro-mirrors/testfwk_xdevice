//
// Copyright (c) 2022 Huawei Device Co., Ltd.
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

const popoverCheckBox = {
  name: "popover-checkbox",
  component: {
    template: `<el-popover placement="bottom" trigger="click">
    <el-checkbox
      :indeterminate="isIndeterminate"
      v-model="checkAll"
      @change="checkAllChange"
      >ALL
    </el-checkbox>
    <el-input v-model="keyword" placeholder="filter" />
    <el-scrollbar max-height="200px">
      <div style="margin: 15px 0"></div>
      <el-checkbox-group v-model="checkedValues" @change="checkedChange">
        <el-checkbox v-for="item in filterOption" :label="item" :key="item" style="display:block">
          {{ item }}
        </el-checkbox>
      </el-checkbox-group>
    </el-scrollbar>

    <div style="text-align: center; margin: 0">
      <el-button size="small" type="primary" @click="reset" link>Reset </el-button>
      <el-button type="primary" size="small" @click="confirm">Confirm </el-button>
    </div>
    <template #reference>
      <span ref="arrowRef" class="arrow">
        {{ headername }}
        <el-icon v-show="checkedValues.length" color="#409EFF"><ArrowDown /></el-icon>
        <el-icon v-show="!checkedValues.length"><ArrowDown /></el-icon>
      </span>
    </template>
  </el-popover>`,
    data() {
      return {
        checkedValues: [],
        checkAll: false,
        isIndeterminate: false,
        keyword: "",
      };
    },
    emits: ["change"],
    props: ["headername", "options", "type"],
    mounted() {
      if (!window.emitter) {
        window.emitter = window.mitt();
      }
      window.emitter.on("filter-name", (data) => {
        if (this.type === data.type) {
          this.checkedValues.length = 0;
          this.isIndeterminate = false;
          this.checkedValues.push(data.value);
          this.$emit("change", this.checkedValues);
        }
      });
    },
    computed: {
      filterOption() {
        if (this.keyword) {
          const val = this.keyword.toLowerCase();
          const result = this.options.filter((item) => {
            return item.toLowerCase().includes(val);
          });
          return result;
        } else {
          const values = this.options ?? [];
          return [...values];
        }
      },
    },
    methods: {
      checkedChange(val) {
        const checkCount = val.length;
        const optionCount = this.filterOption.length || 0;
        this.checkAll = checkCount === optionCount;
        this.isIndeterminate = checkCount > 0 && checkCount < optionCount;
      },
      reset() {
        this.checkedValues.length = 0;
        this.isIndeterminate = false;
        this.checkAll = false;
        this.$emit("change", this.checkedValues);
        this.$refs.arrowRef.click();
      },
      confirm() {
        this.$emit("change", this.checkedValues);
        this.$refs.arrowRef.click();
      },
      checkAllChange(val) {
        this.checkedValues = val ? this.filterOption : [];
        this.isIndeterminate = false;
      },
    },
  },
};
